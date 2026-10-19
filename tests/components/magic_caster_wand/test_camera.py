"""Tests for the spell camera's sample handling and frame rendering."""

from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

from custom_components.magic_caster_wand.camera import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    McwSpellCamera,
    _text_overlay,
)
from custom_components.magic_caster_wand.mcw_ble.spell_tracker import SpellTracker


def _camera_for_render_tests() -> McwSpellCamera:
    camera = object.__new__(McwSpellCamera)
    camera._render_timer = None
    camera._render_task = None
    camera._render_dirty = False
    camera._last_render_time = None
    camera._is_removed = False
    camera._viewer_count = 0
    camera._snapshot_waiters = 0
    camera._state_version = 1
    camera._rendered_state_version = 0
    camera._rendering_state_version = None
    camera._frame_id = 0
    camera._frame_cond = asyncio.Condition()
    return camera


def test_render_frame_returns_canvas_sized_jpeg():
    """A frame snapshot renders as a valid JPEG at the configured dimensions."""
    frame = McwSpellCamera._render_frame(((), None, False, "", True, True, 1))

    with Image.open(io.BytesIO(frame)) as image:
        assert image.format == "JPEG"
        assert image.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_text_overlay_reuses_cached_layer():
    """Repeated labels reuse their small transparent image layer."""
    first = _text_overlay("READY", "white", 56)
    second = _text_overlay("READY", "white", 56)

    assert first is second


def test_text_overlay_fits_measured_text():
    """The layer is wider than the text so glyphs are never clipped, and longer spells get wider layers."""
    short = _text_overlay("LUMOS", "gold", 72)
    long = _text_overlay("WINGARDIUM LEVIOSA", "gold", 72)

    assert long.width > short.width
    assert short.getbbox() is not None
    left, _, right, _ = short.getbbox()
    assert left > 0 and right < short.width


def test_coordinator_update_only_schedules_a_render():
    """The camera redraws from the device's tracker instead of tracking IMU samples itself."""
    camera = _camera_for_render_tests()
    camera.coordinator = SimpleNamespace(data=[{"accel_x": 1.0}])
    camera._schedule_render = Mock()

    camera._handle_coordinator_update()

    assert camera._state_version == 2
    camera._schedule_render.assert_called_once_with()


def test_coordinator_update_ignores_empty_batches():
    camera = _camera_for_render_tests()
    camera.coordinator = SimpleNamespace(data=[])
    camera._schedule_render = Mock()

    camera._handle_coordinator_update()

    assert camera._state_version == 1
    camera._schedule_render.assert_not_called()


async def test_render_snapshot_centers_and_clamps_the_device_trail(hass, monkeypatch):
    """Tracker coordinates are mapped onto the canvas when the frame is captured."""
    camera = _camera_for_render_tests()
    camera._hass = hass
    camera._spell_coordinator = SimpleNamespace(data="awaiting")
    camera._buttons_coordinator = SimpleNamespace(data={"button_all": True})
    camera._mcw = SimpleNamespace(
        has_spell_tracker=True,
        server_reachable=True,
        cast_trail=((10.0, 20.0), (10000.0, -10000.0)),
        cast_point=(10000.0, -10000.0),
    )
    camera._render_dirty = True
    camera._async_render = Mock(return_value=asyncio.sleep(0))

    camera._start_render()

    snapshot = camera._async_render.call_args.args[0]
    assert snapshot[0] == ((CANVAS_WIDTH / 2 + 10.0, CANVAS_HEIGHT / 2 + 20.0), (CANVAS_WIDTH, 0))
    assert snapshot[1] == (CANVAS_WIDTH, 0)
    assert snapshot[2] is True


def test_tracker_skips_intermediate_position_projection_without_changing_final_point():
    """Skipping display-only points keeps the integrated attitude and final cursor exact."""
    full_tracker = SpellTracker(detector=None)
    sparse_tracker = SpellTracker(detector=None)
    full_tracker.start()
    sparse_tracker.start()
    samples = [(0.01 * index, 0.02 * index, 1.0, 0.1, 0.2, 0.3) for index in range(1, 9)]

    for index, sample in enumerate(samples):
        full_point = full_tracker.update(*sample)
        sparse_point = sparse_tracker.update(*sample, calculate_position=index == len(samples) - 1)

    assert sparse_point == full_point
    assert (
        *sparse_tracker._state.orientation.attitude,
    ) == (
        *full_tracker._state.orientation.attitude,
    )


async def test_render_requests_during_interval_share_one_timer(hass, monkeypatch):
    """A burst of changes should leave only one delayed render scheduled."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._viewer_count = 1
        loop = asyncio.get_running_loop()
        camera._last_render_time = loop.time()
        camera._start_render = Mock()

        camera._schedule_render()
        timer = camera._render_timer
        camera._schedule_render()

        assert camera._render_timer is timer
        assert camera._start_render.call_count == 0
        timer.cancel()

    await run_test()


async def test_render_requests_during_active_render_are_coalesced(hass, monkeypatch):
    """Changes made during executor work request one later latest-state frame."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._hass = hass
        monkeypatch.setattr(hass, "async_add_executor_job", lambda func, snapshot: asyncio.sleep(0, result=b"jpeg"))
        camera._frame_cond = asyncio.Condition()
        camera.async_write_ha_state = Mock()
        camera._render_frame = Mock(return_value=b"jpeg")
        camera._render_task = asyncio.current_task()
        camera._rendering_state_version = 1
        camera._viewer_count = 1
        camera._render_dirty = True
        camera._start_render = Mock()
        camera._schedule_render = Mock()

        await camera._async_render(((), None, False, "", True, True, 1))

        assert camera._last_image == b"jpeg"
        camera.async_write_ha_state.assert_not_called()
        camera._schedule_render.assert_called_once_with(force=False)

    await run_test()


def test_imu_updates_without_viewers_do_not_schedule_render():
    """The camera continues tracking but does not render without a consumer."""
    camera = _camera_for_render_tests()
    camera._viewer_count = 0
    camera._render_task = None
    camera._schedule_render()

    assert camera._render_task is None
    assert camera._render_timer is None
    assert not camera._render_dirty


def test_button_update_advances_render_state_without_imu_data():
    """Button events redraw the canvas independently of IMU batches."""
    camera = _camera_for_render_tests()
    camera._schedule_render = Mock()

    camera._handle_buttons_update()

    assert camera._state_version == 2
    camera._schedule_render.assert_called_once_with()


async def test_async_camera_image_renders_on_demand(hass, monkeypatch):
    """A snapshot request renders current state even without an MJPEG viewer."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._frame_cond = asyncio.Condition()
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._buttons_coordinator = SimpleNamespace(data={"button_all": False})
        camera._mcw = SimpleNamespace(has_spell_tracker=False, server_reachable=False, cast_trail=(), cast_point=None)
        camera.async_write_ha_state = Mock()

        async def run_executor(func, snapshot):
            await asyncio.sleep(0)
            return func(snapshot)

        camera._hass = hass
        monkeypatch.setattr(hass, "async_add_executor_job", run_executor)

        image = await camera.async_camera_image()

        assert image.startswith(b"\xff\xd8")
        assert camera._rendered_state_version == camera._state_version
        assert camera._frame_id == 1

    await run_test()


async def test_newer_snapshot_waits_for_followup_when_an_older_render_is_active(hass, monkeypatch):
    """A snapshot request keeps the renderer alive for its newer target version."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._buttons_coordinator = SimpleNamespace(data={"button_all": False})
        camera._mcw = SimpleNamespace(has_spell_tracker=False, server_reachable=False, cast_trail=(), cast_point=None)
        camera.async_write_ha_state = Mock()
        started = asyncio.Event()
        release = asyncio.Event()
        render_versions = []

        def render(snapshot):
            render_versions.append(snapshot[6])
            return f"jpeg-{snapshot[6]}".encode()

        camera._render_frame = render

        async def run_executor(func, snapshot):
            if not started.is_set():
                started.set()
                await release.wait()
            return func(snapshot)

        camera._hass = hass
        monkeypatch.setattr(hass, "async_add_executor_job", run_executor)
        camera._schedule_render(force=True)
        await started.wait()

        camera._state_version = 2
        snapshot_task = asyncio.create_task(camera.async_camera_image())
        await asyncio.sleep(0)
        release.set()
        image = await asyncio.wait_for(snapshot_task, timeout=1)

        assert image == b"jpeg-2"
        assert render_versions == [1, 2]
        assert camera._snapshot_waiters == 0

    await run_test()


async def test_failed_snapshot_render_is_retried_by_the_next_request(hass, monkeypatch):
    """A failed JPEG attempt returns the cache but leaves the version retryable."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._last_image = b"old jpeg"
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._buttons_coordinator = SimpleNamespace(data={"button_all": False})
        camera._mcw = SimpleNamespace(has_spell_tracker=False, server_reachable=False, cast_trail=(), cast_point=None)
        camera.async_write_ha_state = Mock()
        attempts = 0

        def render(snapshot):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary render failure")
            return b"new jpeg"

        camera._render_frame = render

        async def run_executor(func, snapshot):
            await asyncio.sleep(0)
            return func(snapshot)

        camera._hass = hass
        monkeypatch.setattr(hass, "async_add_executor_job", run_executor)

        assert await camera.async_camera_image() == b"old jpeg"
        assert camera._rendered_state_version == 0
        assert camera._failed_state_version == 1
        assert await asyncio.wait_for(camera.async_camera_image(), timeout=1) == b"new jpeg"
        assert attempts == 2
        assert camera._rendered_state_version == 1

    await run_test()


async def test_last_mjpeg_viewer_does_not_cancel_a_waiting_snapshot_timer(hass, monkeypatch):
    """A snapshot waiter keeps a throttled render alive after stream disconnect."""

    class FailingResponse:
        async def prepare(self, request):
            pass

        async def write(self, data):
            raise ConnectionResetError

    async def run_test():
        camera = _camera_for_render_tests()
        camera._frame_id = 1
        camera._last_image = b"old jpeg"
        camera._state_version = 2
        camera._rendered_state_version = 1
        camera._last_render_time = asyncio.get_running_loop().time()
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._buttons_coordinator = SimpleNamespace(data={"button_all": False})
        camera._mcw = SimpleNamespace(has_spell_tracker=False, server_reachable=False, cast_trail=(), cast_point=None)
        camera._render_frame = Mock(return_value=b"new jpeg")
        camera.async_write_ha_state = Mock()

        async def run_executor(func, snapshot):
            await asyncio.sleep(0)
            return func(snapshot)

        camera._hass = hass
        monkeypatch.setattr(hass, "async_add_executor_job", run_executor)
        camera._schedule_render(force=True)
        render_timer = camera._render_timer
        snapshot_task = asyncio.create_task(camera.async_camera_image())
        await asyncio.sleep(0)
        assert camera._snapshot_waiters == 1

        aiohttp_module = sys.modules["aiohttp"]
        previous_web = aiohttp_module.web
        aiohttp_module.web = SimpleNamespace(StreamResponse=FailingResponse)
        camera._request_latest_render = Mock()
        try:
            await camera.handle_async_mjpeg_stream(object())
            assert camera._viewer_count == 0
            assert camera._render_timer is render_timer
            assert not render_timer.cancelled()
            assert await asyncio.wait_for(snapshot_task, timeout=1) == b"new jpeg"
        finally:
            aiohttp_module.web = previous_web

    await run_test()


async def test_mjpeg_stream_sends_cached_first_frame_and_tracks_viewer(hass, monkeypatch):
    """A new stream receives a frame immediately and unregisters on cancellation."""

    class FakeResponse:
        def __init__(self):
            self.writes = []
            self.first_frame_sent = asyncio.Event()

        async def prepare(self, request):
            pass

        async def write(self, data):
            self.writes.append(data)
            if len(self.writes) == 3:
                self.first_frame_sent.set()

    async def run_test():
        camera = _camera_for_render_tests()
        camera._frame_cond = asyncio.Condition()
        camera._last_image = b"cached jpeg"
        response = FakeResponse()
        camera._request_latest_render = Mock()
        aiohttp_module = sys.modules["aiohttp"]
        previous_web = aiohttp_module.web
        aiohttp_module.web = SimpleNamespace(StreamResponse=lambda: response)
        try:
            task = asyncio.create_task(camera.handle_async_mjpeg_stream(object()))
            await asyncio.wait_for(response.first_frame_sent.wait(), timeout=1)
            assert response.writes[1] == b"cached jpeg"
            assert camera._viewer_count == 1

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert camera._viewer_count == 0
        finally:
            aiohttp_module.web = previous_web

    await run_test()


async def test_removal_cancels_timer_and_active_render(hass, monkeypatch):
    """Unloading the entity cancels pending timers and render tasks."""

    async def run_test():
        camera = _camera_for_render_tests()
        timer = asyncio.get_running_loop().call_later(60, Mock())
        camera._render_timer = timer
        camera._render_dirty = True

        async def active_render():
            await asyncio.Future()

        render_task = asyncio.create_task(active_render())
        camera._render_task = render_task
        await camera.async_will_remove_from_hass()

        assert camera._is_removed
        assert timer.cancelled()
        assert camera._render_timer is None
        assert camera._render_task is None
        assert not camera._render_dirty
        assert render_task.cancelled()

    await run_test()
