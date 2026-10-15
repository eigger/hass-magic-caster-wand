"""Support for Magic Caster Wand BLE camera."""

from __future__ import annotations

import asyncio
import io
import logging
from functools import lru_cache

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from PIL import Image, ImageDraw, ImageFont

from .const import MANUFACTURER
from .runtime_data import MagicCasterWandConfigEntry, McwRuntimeData

_LOGGER = logging.getLogger(__name__)

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
MAX_RENDER_FPS = 10
MIN_FRAME_INTERVAL = 1 / MAX_RENDER_FPS


TEXT_PADDING = 4


@lru_cache(maxsize=8)
def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Return the default font at the requested pixel size."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 only ships the fixed-size bitmap font
        return ImageFont.load_default()


@lru_cache(maxsize=64)
def _text_overlay(text: str, fill: str | tuple[int, int, int, int], size: int) -> Image.Image:
    """Return a cached transparent text layer sized to the measured text, so nothing is clipped."""
    font = _font(size)
    left, top, right, bottom = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    overlay = Image.new(
        "RGBA",
        (right - left + 2 * TEXT_PADDING, bottom - top + 2 * TEXT_PADDING),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(overlay).text((TEXT_PADDING - left, TEXT_PADDING - top), text, fill=fill, font=font)
    return overlay


def _to_canvas(point: tuple[float, float]) -> tuple[float, float]:
    """Center a tracker coordinate on the canvas and clamp it to the frame."""
    return (
        max(0, min(CANVAS_WIDTH, point[0] + CANVAS_WIDTH / 2)),
        max(0, min(CANVAS_HEIGHT, point[1] + CANVAS_HEIGHT / 2)),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MagicCasterWandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE camera."""
    data = entry.runtime_data
    if isinstance(data, McwRuntimeData):
        async_add_entities(
            [
                McwSpellCamera(
                    hass,
                    data.address,
                    data.device,
                    data.imu_coordinator,
                    data.buttons_coordinator,
                    data.spell_coordinator,
                    data.connection_coordinator,
                )
            ]
        )


class McwSpellCamera(CoordinatorEntity, Camera):
    """Camera entity for visualizing spell tracking."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[list[dict[str, float]]],
        buttons_coordinator: DataUpdateCoordinator[dict[str, bool]],
        spell_coordinator: DataUpdateCoordinator[str],
        connection_coordinator: DataUpdateCoordinator[bool],
    ) -> None:
        """Initialize the spell camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._buttons_coordinator = buttons_coordinator
        self._spell_coordinator = spell_coordinator
        self._connection_coordinator = connection_coordinator
        self._identifier = address.replace(":", "")[-8:]
        self._attr_translation_key = "spell_canvas"
        self._attr_unique_id = f"mcw_{self._identifier}_camera"

        self._last_image = None
        self._frame_cond = asyncio.Condition()
        self._render_timer = None
        self._render_task = None
        self._render_dirty = False
        self._last_render_time = None
        self._is_removed = False
        self._viewer_count = 0
        self._snapshot_waiters = 0
        self._state_version = 1
        self._rendered_state_version = 0
        self._failed_state_version = 0
        self._rendering_state_version = None
        self._frame_id = 0

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        # Initialize default image
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "black")
        self._last_image = self._image_to_bytes(img)
        # Register connection coordinator listener
        self.async_on_remove(self._connection_coordinator.async_add_listener(self._handle_connection_update))
        self.async_on_remove(self._buttons_coordinator.async_add_listener(self._handle_buttons_update))
        self.async_on_remove(self._spell_coordinator.async_add_listener(self._handle_spell_update))

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending camera rendering before the entity is removed."""
        self._is_removed = True
        if self._render_timer is not None:
            self._render_timer.cancel()
            self._render_timer = None
        self._render_dirty = False

        render_task = self._render_task
        self._render_task = None
        if render_task is not None:
            render_task.cancel()
            try:
                await render_task
            except asyncio.CancelledError:
                pass

        async with self._frame_cond:
            self._frame_cond.notify_all()

        await super().async_will_remove_from_hass()

    @callback
    def _handle_connection_update(self) -> None:
        """Handle connection state changes."""
        self.async_write_ha_state()

    @callback
    def _handle_buttons_update(self) -> None:
        """Redraw when button state changes, even without IMU data."""
        self._state_version += 1
        self._schedule_render()

    @callback
    def _handle_spell_update(self) -> None:
        """Refresh the displayed spell when recognition completes."""
        self._state_version += 1
        self._schedule_render()

    @property
    def _button_all(self) -> bool:
        """Whether all buttons are held, i.e. a cast is being drawn."""
        buttons = self._buttons_coordinator.data
        return bool(buttons and buttons.get("button_all", False))

    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL image to bytes."""
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster {self._mcw.device_label} {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._connection_coordinator.data is True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Redraw from the path the device's tracker has already computed for this batch."""
        if not self.coordinator.data:
            return
        self._state_version += 1
        self._schedule_render()

    @callback
    def _schedule_render(self, *, force: bool = False) -> None:
        """Schedule one render, coalescing IMU updates to the maximum frame rate."""
        if self._is_removed or (self._viewer_count == 0 and not force):
            return
        self._render_dirty = True
        if self._render_timer is not None or self._render_task is not None:
            return

        loop = asyncio.get_running_loop()
        if self._last_render_time is not None:
            delay = MIN_FRAME_INTERVAL - (loop.time() - self._last_render_time)
            if delay > 0:
                self._render_timer = loop.call_later(delay, self._start_render)
                return

        self._start_render()

    @callback
    def _start_render(self) -> None:
        """Capture event-loop-owned state and start a single background render."""
        self._render_timer = None
        if self._is_removed or not self._render_dirty or self._render_task is not None:
            return

        self._render_dirty = False
        spell_name = self._spell_coordinator.data or "awaiting"
        spell_name = "" if spell_name == "awaiting" else spell_name.replace("_", " ").upper()
        has_tracker = getattr(self._mcw, "has_spell_tracker", False)
        server_reachable = getattr(self._mcw, "server_reachable", False)
        snapshot = (
            tuple(_to_canvas(point) for point in self._mcw.cast_trail),
            _to_canvas(self._mcw.cast_point) if self._mcw.cast_point is not None else None,
            self._button_all,
            spell_name,
            server_reachable,
            has_tracker,
            self._state_version,
        )
        self._failed_state_version = 0
        self._rendering_state_version = self._state_version
        self._render_task = self._hass.async_create_task(self._async_render(snapshot))

    async def _async_render(self, snapshot: tuple) -> None:
        """Render a captured frame away from the Home Assistant event loop."""
        try:
            image_bytes = await self._hass.async_add_executor_job(self._render_frame, snapshot)
        except Exception:
            _LOGGER.exception("Failed to render spell camera frame")
            if not self._is_removed:
                self._failed_state_version = max(self._failed_state_version, snapshot[6])
                async with self._frame_cond:
                    self._frame_cond.notify_all()
        else:
            if not self._is_removed:
                self._last_image = image_bytes
                self._rendered_state_version = max(self._rendered_state_version, snapshot[6])
                self._frame_id += 1
                async with self._frame_cond:
                    self._frame_cond.notify_all()
        finally:
            self._last_render_time = asyncio.get_running_loop().time()
            self._render_task = None
            self._rendering_state_version = None
            if self._render_dirty and not self._is_removed and (self._viewer_count > 0 or self._snapshot_waiters > 0):
                self._schedule_render(force=self._viewer_count == 0)

    @staticmethod
    def _render_frame(snapshot: tuple) -> bytes:
        """Render an immutable camera state snapshot to JPEG bytes."""
        points, last_point, button_all, spell_name, server_reachable, has_tracker, _state_version = snapshot
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "black")
        draw = ImageDraw.Draw(img)

        if not has_tracker:
            server_text, server_color = "MODEL MISSING", "orange"
        elif server_reachable:
            server_text, server_color = "SERVER OK", "lime"
        else:
            server_text, server_color = "SERVER ERROR", "red"

        server_layer = _text_overlay(server_text, server_color, 24)
        img.paste(server_layer, (10, 10), server_layer)

        status_text = "TRACKING" if button_all else "READY"
        status_layer = _text_overlay(status_text, "red" if button_all else "white", 56)
        img.paste(status_layer, ((CANVAS_WIDTH - status_layer.width) // 2, 20), status_layer)

        if spell_name and not button_all:
            spell_size = 72
            spell_layer = _text_overlay(spell_name, "gold", spell_size)
            while spell_layer.width > CANVAS_WIDTH - 20 and spell_size > 16:
                spell_size -= 4
                spell_layer = _text_overlay(spell_name, "gold", spell_size)
            img.paste(spell_layer, ((CANVAS_WIDTH - spell_layer.width) // 2, 100), spell_layer)

        desc_layer = _text_overlay("PRESS ALL BUTTONS TO DRAW", (150, 150, 150, 255), 22)
        img.paste(desc_layer, ((CANVAS_WIDTH - desc_layer.width) // 2, CANVAS_HEIGHT - 50), desc_layer)

        if len(points) > 1:
            draw.line(points, fill="cyan", width=2)
        if last_point:
            draw.ellipse([last_point[0] - 5, last_point[1] - 5, last_point[0] + 5, last_point[1] + 5], fill="yellow")

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from aiohttp import web

        response = web.StreamResponse()
        response.content_type = "multipart/x-mixed-replace;boundary=--frame"
        self._viewer_count += 1
        try:
            self._request_latest_render()
            await response.prepare(request)
            last_frame_id = -1
            while True:
                async with self._frame_cond:
                    await self._frame_cond.wait_for(
                        lambda frame_id=last_frame_id: self._frame_id > frame_id or self._is_removed
                    )
                    if self._is_removed:
                        break
                    img_bytes = self._last_image
                    last_frame_id = self._frame_id

                await response.write(
                    f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(img_bytes)}\r\n\r\n".encode()
                )
                await response.write(img_bytes)
                await response.write(b"\r\n")
        except ConnectionResetError:
            return response
        except asyncio.CancelledError:
            raise
        finally:
            self._viewer_count -= 1
            if self._viewer_count == 0 and self._snapshot_waiters == 0 and self._render_timer is not None:
                self._render_timer.cancel()
                self._render_timer = None
                self._render_dirty = False

        return response

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image response from the camera."""
        self._snapshot_waiters += 1
        try:
            target_version = self._state_version
            if self._rendered_state_version < target_version and (
                self._render_task is None or self._rendering_state_version < target_version
            ):
                self._failed_state_version = 0
                self._schedule_render(force=True)
            async with self._frame_cond:
                await self._frame_cond.wait_for(
                    lambda: (
                        self._rendered_state_version >= target_version
                        or self._failed_state_version >= target_version
                        or self._is_removed
                    )
                )
            return self._last_image
        finally:
            self._snapshot_waiters -= 1
            if self._viewer_count == 0 and self._snapshot_waiters == 0:
                self._cancel_idle_render()

    @callback
    def _cancel_idle_render(self) -> None:
        """Cancel a delayed render when no stream or snapshot needs another frame."""
        if self._render_timer is not None:
            self._render_timer.cancel()
            self._render_timer = None
        self._render_dirty = False

    @callback
    def _request_latest_render(self) -> None:
        """Render current state if no equal-or-newer frame is already in progress."""
        target_version = self._state_version
        if self._rendered_state_version < target_version and (
            self._render_task is None or self._rendering_state_version < target_version
        ):
            self._failed_state_version = 0
            self._schedule_render(force=True)

    def camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image response from the camera."""
        return self._last_image
