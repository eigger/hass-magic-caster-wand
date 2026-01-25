"""Support for Magic Caster Wand BLE camera."""
from __future__ import annotations

import asyncio
import io
import logging
from collections import deque

from PIL import Image, ImageDraw

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUFACTURER
from .mcw_ble.spell_tracker import SpellTracker

_LOGGER = logging.getLogger(__name__)

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
TRAIL_LENGTH = 1000

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE camera."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    mcw = data["mcw"]
    imu_coordinator = data["imu_coordinator"]
    buttons_coordinator = data["buttons_coordinator"]
    spell_coordinator = data["spell_coordinator"]

    async_add_entities([McwSpellCamera(hass, address, mcw, imu_coordinator, buttons_coordinator, spell_coordinator)])


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
        spell_coordinator: DataUpdateCoordinator[str]
    ) -> None:
        """Initialize the spell camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._buttons_coordinator = buttons_coordinator
        self._spell_coordinator = spell_coordinator
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Spell Canvas"
        self._attr_unique_id = f"mcw_{self._identifier}_camera"
        
        # Spell tracking components
        self._tracker = SpellTracker(detector=None)
        self._tracker.start() # Start tracker for initial cursor positioning
        self._trail = deque(maxlen=TRAIL_LENGTH)
        self._last_point = None
        self._last_image = None
        self._prev_button_all = False
        self._frame_cond = asyncio.Condition()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        # Initialize default image
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "black")
        self._last_image = self._image_to_bytes(img)

    def _clear_canvas(self):
        """Clear the drawing canvas."""
        self._trail.clear()
        self._tracker.start()
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "black")
        self._last_image = self._image_to_bytes(img)

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
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        imu_data = self.coordinator.data
        if not imu_data:
            return

        # Get current button state
        button_all = False
        if self._buttons_coordinator.data:
            button_all = self._buttons_coordinator.data.get("button_all", False)

        # Handle button_all transition (imuvisualizer style)
        if button_all and not self._prev_button_all:
            _LOGGER.debug("Buttons pressed - starting new trail")
            self._trail.clear()
            self._tracker.start()
        
        self._prev_button_all = button_all

        for sample in imu_data:
            # imuvisualizer.py logic for coordinate transformation
            point = self._tracker.update(
                ax=sample['accel_y'],
                ay=-sample['accel_x'],
                az=sample['accel_z'],
                gx=sample['gyro_y'],
                gy=-sample['gyro_x'],
                gz=sample['gyro_z']
            )
            
            if point:
                # Center + scale (roughly)
                x = point[0] + (CANVAS_WIDTH / 2)
                y = point[1] + (CANVAS_HEIGHT / 2)
                
                # Clamp
                x = max(0, min(CANVAS_WIDTH, x))
                y = max(0, min(CANVAS_HEIGHT, y))
                
                self._last_point = (x, y)
                if button_all:
                    self._trail.append((x, y))

        # Render the trail
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "black")
        draw = ImageDraw.Draw(img)
        
        # Get detected spell name
        spell_name = self._spell_coordinator.data or "awaiting"
        if spell_name == "awaiting":
            spell_name = ""
        else:
            spell_name = spell_name.replace("_", " ").upper()

        # Server Status (Top Left)
        server_reachable = getattr(self._mcw, "server_reachable", False)
        has_tracker = getattr(self._mcw, "_spell_tracker", None) is not None
        
        if not has_tracker:
            server_text = "MODEL MISSING"
            server_color = "orange"
        elif server_reachable:
            server_text = "SERVER OK"
            server_color = "lime"
        else:
            server_text = "SERVER ERROR"
            server_color = "red"

        # Draw Server Status
        srv_tw = (len(server_text) * 6) + 4
        srv_img = Image.new("RGBA", (srv_tw, 15), (0, 0, 0, 0))
        srv_draw = ImageDraw.Draw(srv_img)
        srv_draw.text((2, 0), server_text, fill=server_color)
        
        srv_scale = 2
        scaled_srv = srv_img.resize((srv_tw * srv_scale, 15 * srv_scale), resample=Image.NEAREST)
        img.paste(scaled_srv, (10, 10), scaled_srv)

        # Add status text (Perfectly Centered)
        status_text = "TRACKING" if button_all else "READY"
        # Since we might not have a font, we draw small and upscale
        text_color = "red" if button_all else "white"
        
        # Calculate actual text width to center it
        # We'll draw on a wider canvas first to measure
        measure_img = Image.new("RGBA", (400, 20), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_img)
        # Assuming default font size is roughly 6x10 per char
        # A more robust way without font is to use the text bbox if available, 
        # but since we draw small and upscale, we can just estimate or use a helper
        tw = (len(status_text) * 6) + 4 # Added padding
        
        # Create a small image for text that fits the text
        txt_img = Image.new("RGBA", (tw, 15), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((2, 0), status_text, fill=text_color) # Offset x to avoid left cutoff
        
        # Scale up (e.g., 4x for big effect)
        scale_factor = 4
        scaled_txt = txt_img.resize((tw * scale_factor, 15 * scale_factor), resample=Image.NEAREST)
        
        # Calculate center position
        txt_x = (CANVAS_WIDTH - (tw * scale_factor)) // 2
        img.paste(scaled_txt, (txt_x, 20), scaled_txt)

        # Add Spell Name if detected and NOT currently tracking
        if spell_name and not button_all:
            # Draw spell name in the center
            spell_tw = (len(spell_name) * 8) + 20 # Safer width and more padding
            spell_img = Image.new("RGBA", (spell_tw, 15), (0, 0, 0, 0))
            spell_draw = ImageDraw.Draw(spell_img)
            spell_draw.text((10, 0), spell_name, fill="gold") # More horizontal offset
            
            # Scale up big
            spell_scale = 5
            scaled_spell = spell_img.resize((spell_tw * spell_scale, 15 * spell_scale), resample=Image.NEAREST)
            
            spell_x = (CANVAS_WIDTH - (spell_tw * spell_scale)) // 2
            spell_y = 90  # Just below the status text (which is at y=20 and scaled up)
            img.paste(scaled_spell, (spell_x, spell_y), scaled_spell)
        
        # Add bottom description (Centered)
        desc_text = "PRESS ALL BUTTONS TO DRAW"
        desc_tw = len(desc_text) * 6
        desc_img = Image.new("RGBA", (desc_tw, 15), (0, 0, 0, 0))
        desc_draw = ImageDraw.Draw(desc_img)
        desc_draw.text((0, 0), desc_text, fill=(150, 150, 150, 255)) # Subtle gray
        
        # Scale up less than the status (e.g., 2x)
        desc_scale = 2
        scaled_desc = desc_img.resize((desc_tw * desc_scale, 15 * desc_scale), resample=Image.NEAREST)
        
        desc_x = (CANVAS_WIDTH - (desc_tw * desc_scale)) // 2
        img.paste(scaled_desc, (desc_x, CANVAS_HEIGHT - 40), scaled_desc)
        
        # Draw trail
        if len(self._trail) > 1:
            points = list(self._trail)
            draw.line(points, fill="cyan", width=2)
            
        # Draw cursor at last known point
        if self._last_point:
            lp = self._last_point
            draw.ellipse([lp[0]-5, lp[1]-5, lp[0]+5, lp[1]+5], fill="yellow")
        
        self._last_image = self._image_to_bytes(img)
        self.async_write_ha_state()

        async def _notify():
            async with self._frame_cond:
                self._frame_cond.notify_all()
        
        self._hass.async_create_task(_notify())

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from aiohttp import web

        response = web.StreamResponse()
        response.content_type = "multipart/x-mixed-replace;boundary=--frame"
        await response.prepare(request)

        try:
            while True:
                async with self._frame_cond:
                    await self._frame_cond.wait()
                    img_bytes = self._last_image

                await response.write(
                    f"--frame\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(img_bytes)}\r\n\r\n".encode()
                )
                await response.write(img_bytes)
                await response.write(b"\r\n")
        except (ConnectionResetError, asyncio.CancelledError):
            return response

        return response

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return self._last_image

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return self._last_image
