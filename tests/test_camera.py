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
    camera._is_removed = False
    return camera


def test_render_frame_returns_canvas_sized_jpeg():
    """A frame snapshot renders as a valid JPEG at the configured dimensions."""
    frame = McwSpellCamera._render_frame(((), None, False, "", True, True))

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
        camera._render_dirty = True
        camera._start_render = Mock()
        camera._schedule_render = Mock()

        await camera._async_render(())

        assert camera._last_image == b"jpeg"
        camera._schedule_render.assert_called_once_with()

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
