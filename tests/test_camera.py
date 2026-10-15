"""Tests for the spell camera's sample handling and frame rendering."""

from __future__ import annotations

import asyncio
import io
import sys
from collections import deque
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

from PIL import Image


class _Base:
    """Minimal Home Assistant base class for importing the entity module."""

    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

    async def async_will_remove_from_hass(self):
        pass


class _CameraBase(_Base):
    pass


class _CoordinatorBase(_Base):
    pass


camera_module = ModuleType("homeassistant.components.camera")
camera_module.Camera = _CameraBase
sys.modules["homeassistant.components.camera"] = camera_module

entity_platform_module = ModuleType("homeassistant.helpers.entity_platform")
entity_platform_module.AddEntitiesCallback = _Base
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_module

coordinator_module = sys.modules["homeassistant.helpers.update_coordinator"]
coordinator_module.CoordinatorEntity = _CoordinatorBase
coordinator_module.DataUpdateCoordinator = _Base

sys.modules["homeassistant.core"].callback = lambda func: func

from custom_components.magic_caster_wand.camera import CANVAS_HEIGHT, CANVAS_WIDTH, McwSpellCamera  # noqa: E402


def _camera_for_render_tests() -> McwSpellCamera:
    camera = object.__new__(McwSpellCamera)
    camera._render_timer = None
    camera._render_task = None
    camera._render_dirty = False
    camera._last_render_time = None
    camera._prev_button_all = False
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


def test_coordinator_update_processes_every_sample_before_scheduling_render():
    """Frame coalescing must not skip any IMU samples used by the tracker."""
    camera = _camera_for_render_tests()
    samples = [
        {
            "accel_x": 1.0,
            "accel_y": 2.0,
            "accel_z": 3.0,
            "gyro_x": 4.0,
            "gyro_y": 5.0,
            "gyro_z": 6.0,
        }
        for _ in range(3)
    ]
    camera.coordinator = SimpleNamespace(data=samples)
    camera._buttons_coordinator = SimpleNamespace(data={"button_all": True})
    camera._tracker = Mock()
    camera._tracker.update.side_effect = [(10.0, 20.0), (11.0, 21.0), (12.0, 22.0)]
    camera._trail = deque(maxlen=1000)
    camera._last_point = None
    camera._prev_button_all = False
    camera._schedule_render = Mock()

    camera._handle_coordinator_update()

    assert camera._tracker.update.call_count == len(samples)
    assert list(camera._trail) == [
        (CANVAS_WIDTH / 2 + 10.0, CANVAS_HEIGHT / 2 + 20.0),
        (CANVAS_WIDTH / 2 + 11.0, CANVAS_HEIGHT / 2 + 21.0),
        (CANVAS_WIDTH / 2 + 12.0, CANVAS_HEIGHT / 2 + 22.0),
    ]
    camera._schedule_render.assert_called_once_with()


def test_render_requests_during_interval_share_one_timer():
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

    asyncio.run(run_test())


def test_render_requests_during_active_render_are_coalesced():
    """Changes made during executor work request one later latest-state frame."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._hass = SimpleNamespace(async_add_executor_job=lambda func, snapshot: asyncio.sleep(0, result=b"jpeg"))
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
        camera._schedule_render.assert_called_once_with(force=False)

    asyncio.run(run_test())


def test_imu_updates_without_viewers_do_not_schedule_render():
    """The camera continues tracking but does not render without a consumer."""
    camera = _camera_for_render_tests()
    camera._viewer_count = 0
    camera._render_task = None
    camera._schedule_render()

    assert camera._render_task is None
    assert camera._render_timer is None
    assert not camera._render_dirty


def test_button_transition_updates_canvas_without_imu_data():
    """Button events reset the trail and advance the render state independently."""
    camera = _camera_for_render_tests()
    camera._buttons_coordinator = SimpleNamespace(data={"button_all": True})
    camera._tracker = Mock()
    camera._trail = deque([(100.0, 100.0)], maxlen=1000)
    camera._schedule_render = Mock()

    camera._handle_buttons_update()

    camera._tracker.start.assert_called_once_with()
    assert not camera._trail
    assert camera._prev_button_all
    assert camera._state_version == 2
    camera._schedule_render.assert_called_once_with()


def test_async_camera_image_renders_on_demand():
    """A snapshot request renders current state even without an MJPEG viewer."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._frame_cond = asyncio.Condition()
        camera._trail = deque(maxlen=1000)
        camera._last_point = None
        camera._prev_button_all = False
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._mcw = SimpleNamespace(_spell_tracker=None, server_reachable=False)
        camera.async_write_ha_state = Mock()

        async def run_executor(func, snapshot):
            await asyncio.sleep(0)
            return func(snapshot)

        camera._hass = SimpleNamespace(
            async_create_task=asyncio.create_task,
            async_add_executor_job=run_executor,
        )

        image = await camera.async_camera_image()

        assert image.startswith(b"\xff\xd8")
        assert camera._rendered_state_version == camera._state_version
        assert camera._frame_id == 1

    asyncio.run(run_test())


def test_newer_snapshot_waits_for_followup_when_an_older_render_is_active():
    """A snapshot request keeps the renderer alive for its newer target version."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._trail = deque(maxlen=1000)
        camera._last_point = None
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._mcw = SimpleNamespace(_spell_tracker=None, server_reachable=False)
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

        camera._hass = SimpleNamespace(
            async_create_task=asyncio.create_task,
            async_add_executor_job=run_executor,
        )
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

    asyncio.run(run_test())


def test_failed_snapshot_render_is_retried_by_the_next_request():
    """A failed JPEG attempt returns the cache but leaves the version retryable."""

    async def run_test():
        camera = _camera_for_render_tests()
        camera._trail = deque(maxlen=1000)
        camera._last_point = None
        camera._last_image = b"old jpeg"
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._mcw = SimpleNamespace(_spell_tracker=None, server_reachable=False)
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

        camera._hass = SimpleNamespace(
            async_create_task=asyncio.create_task,
            async_add_executor_job=run_executor,
        )

        assert await camera.async_camera_image() == b"old jpeg"
        assert camera._rendered_state_version == 0
        assert camera._failed_state_version == 1
        assert await asyncio.wait_for(camera.async_camera_image(), timeout=1) == b"new jpeg"
        assert attempts == 2
        assert camera._rendered_state_version == 1

    asyncio.run(run_test())


def test_last_mjpeg_viewer_does_not_cancel_a_waiting_snapshot_timer():
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
        camera._trail = deque(maxlen=1000)
        camera._last_point = None
        camera._spell_coordinator = SimpleNamespace(data="awaiting")
        camera._mcw = SimpleNamespace(_spell_tracker=None, server_reachable=False)
        camera._render_frame = Mock(return_value=b"new jpeg")
        camera.async_write_ha_state = Mock()

        async def run_executor(func, snapshot):
            await asyncio.sleep(0)
            return func(snapshot)

        camera._hass = SimpleNamespace(
            async_create_task=asyncio.create_task,
            async_add_executor_job=run_executor,
        )
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

    asyncio.run(run_test())


def test_mjpeg_stream_sends_cached_first_frame_and_tracks_viewer():
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

    asyncio.run(run_test())


def test_removal_cancels_timer_and_active_render():
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

    asyncio.run(run_test())
