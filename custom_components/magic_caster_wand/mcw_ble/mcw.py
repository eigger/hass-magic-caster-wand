# mcw_ble.py
"""BLE client for Magic Caster Wand communication."""

from __future__ import annotations

import logging
import struct
import asyncio
from asyncio import Event, sleep, wait_for
from typing import Any, Callable, TypeVar

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
COMMAND_UUID = "57420002-587e-48a0-974c-544d6163c577"
NOTIFY_UUID = "57420003-587e-48a0-974c-544d6163c577"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

from .macros import Macro, LedGroup

_LOGGER = logging.getLogger(__name__)


class BleakCharacteristicMissing(BleakError):
    """Raised when a characteristic is missing."""


class BleakServiceMissing(BleakError):
    """Raised when a service is missing."""


WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])


def disconnect_on_missing_services(func: WrapFuncType) -> WrapFuncType:
    """Decorator to handle missing services by disconnecting."""

    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except (BleakServiceMissing, BleakCharacteristicMissing):
            try:
                if self.client.is_connected:
                    await self.client.clear_cache()
                    await self.client.disconnect()
            except Exception:
                pass
            raise

    return wrapper  # type: ignore


class McwClient:
    """BLE client for communicating with Magic Caster Wand."""

    def __init__(self, client: BleakClient) -> None:
        """Initialize the client."""
        self.client = client
        self.event: Event = Event()
        self.command_data: bytes | None = None
        self.callback_spell: Callable[[str], None] | None = None
        self.callback_battery: Callable[[float], None] | None = None
        self.callback_buttons: Callable[[dict[str, bool]], None] | None = None
        self.callback_calibration: Callable[[dict[str, bool]], None] | None = None
        self.wand_type: str | None = None
        self.serial_number: str | None = None
        self.sku: str | None = None
        self.firmware: str | None = None
        self.box_address: str | None = None
        self.manufacturer_id: str | None = None
        self.device_id: str | None = None
        self.edition: str | None = None
        self.companion_address: str | None = None
        self.lock = asyncio.Lock()
        
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.client.is_connected

    def register_callback(self, spell_cb: Callable, battery_cb: Callable, buttons_cb: Callable = None, calibration_cb: Callable = None) -> None:
        """Register callbacks for spell, battery, button, and calibration notifications."""
        self.callback_spell = spell_cb
        self.callback_battery = battery_cb
        self.callback_buttons = buttons_cb
        self.callback_calibration = calibration_cb

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        """Start receiving notifications."""
        await self.client.start_notify(NOTIFY_UUID, self._handler)
        await self.client.start_notify(BATTERY_UUID, self._handler_battery)
        await sleep(1.0)

    @disconnect_on_missing_services
    async def stop_notify(self) -> None:
        """Stop receiving notifications."""
        try:
            await self.client.stop_notify(NOTIFY_UUID)
            await self.client.stop_notify(BATTERY_UUID)
        except Exception as err:
            _LOGGER.debug("Error stopping notifications: %s", err)

    @disconnect_on_missing_services
    async def write(self, uuid: str, data: bytes, response: bool = False) -> None:
        """Write data to the specified characteristic."""
        _LOGGER.debug("Write UUID=%s data=%s", uuid, data.hex())
        await self.client.write_gatt_char(uuid, data, response)

    def _handler_battery(self, _: Any, data: bytearray) -> None:
        """Handle battery notification."""
        _LOGGER.debug("Battery received: %s", data.hex())
        battery = int.from_bytes(data, byteorder="little")
        if self.callback_battery:
            self.callback_battery(battery)

    def _handler(self, _: Any, data: bytearray) -> None:
        """Handle notification data."""
        _LOGGER.debug("Received: %s", data.hex())

        if self.command_data is None:
            self.command_data = bytes(data)
            self.event.set()

        if not data or len(data) < 1:
            return

        opcode = data[0]
        if opcode == 0x24:
            self._parse_spell(data)
        elif opcode == 0x10:
            self._parse_buttons(data)
        elif opcode == 0xFB or opcode == 0xFC:
            self._parse_calibration(data)

    def _parse_spell(self, data: bytearray) -> None:
        """Parse spell data from notification."""
        try:
            if len(data) < 5:
                return

            spell_len = data[3]
            raw_name = data[4 : 4 + spell_len]
            spell_name = raw_name.decode("utf-8", errors="ignore").strip()
            spell_name = spell_name.replace("\x00", "").replace("_", " ")

            if not spell_name:
                return

            _LOGGER.debug("Spell detected: %s", spell_name)
            if self.callback_spell:
                self.callback_spell(spell_name)

        except Exception as err:
            _LOGGER.warning("Spell parse error: %s", err)

    def _parse_buttons(self, data: bytearray) -> None:
        """Parse button states from notification.
        
        Format: [0x10, Mask]
        Bit Mask:
            0x01: Button 1 (Big)
            0x02: Button 2
            0x04: Button 3
            0x08: Button 4
        """
        try:
            if len(data) < 2:
                return

            mask = data[1]
            button_states = {
                "button_1": bool(mask & 0x01),
                "button_2": bool(mask & 0x02),
                "button_3": bool(mask & 0x04),
                "button_4": bool(mask & 0x08),
            }

            _LOGGER.debug("Button states: %s (mask=0x%02X)", button_states, mask)
            if self.callback_buttons:
                self.callback_buttons(button_states)

        except Exception as err:
            _LOGGER.warning("Button parse error: %s", err)

    def _parse_calibration(self, data: bytearray) -> None:
        """Parse calibration response from notification.
        
        Format:
            0xFB: Button calibration confirmed
            0xFC: IMU calibration confirmed
        """
        try:
            if len(data) < 1:
                return

            opcode = data[0]
            if opcode == 0xFB:
                _LOGGER.debug("Button calibration confirmed (FB response)")
                if self.callback_calibration:
                    self.callback_calibration({"calibration_button": "Done"})
            elif opcode == 0xFC:
                _LOGGER.debug("IMU calibration confirmed (FC response)")
                if self.callback_calibration:
                    self.callback_calibration({"calibration_imu": "Done"})

        except Exception as err:
            _LOGGER.warning("Calibration parse error: %s", err)

    async def read(self, timeout: float = 5.0) -> bytes:
        """Read response data with timeout."""
        await wait_for(self.event.wait(), timeout)
        return self.command_data or b""

    async def write_command(self, packet: bytes, response: bool = True) -> bytes:
        """Write command and optionally wait for response."""
        async with self.lock:
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                try:
                    if response:
                        self.command_data = None
                        self.event.clear()
                        await self.write(COMMAND_UUID, packet, False)
                        return await self.read()
                    else:
                        await self.write(COMMAND_UUID, packet, False)
                        return b""
                except Exception as err:
                    if attempt < max_retries:
                        _LOGGER.warning(
                            "Write retry (attempt %d/%d): %s", attempt, max_retries, err
                        )
                        await sleep(0.5)
                    else:
                        raise

            return b""

    async def init_wand(self) -> None:
        """Initialize the wand."""
        commands = [
            struct.pack("BBB", 0xDC, 0x00, 0x05),
            struct.pack("BBB", 0xDC, 0x01, 0x05),
            struct.pack("BBB", 0xDC, 0x02, 0x05),
            struct.pack("BBB", 0xDC, 0x03, 0x05),
            struct.pack("BBB", 0xDC, 0x04, 0x08),
            struct.pack("BBB", 0xDC, 0x05, 0x08),
            struct.pack("BBB", 0xDC, 0x06, 0x08),
            struct.pack("BBB", 0xDC, 0x07, 0x08),
        ]
        for cmd in commands:
            await self.write_command(cmd, False)

    async def keep_alive(self) -> None:
        """Send keep-alive command."""
        await self.write_command(struct.pack("B", 0x01), False)
    
    async def calibration(self) -> None:
        """Send calibration commands.
        
        Sends FE 55 AA to start calibration, then FB and FC commands.
        Responses are parsed in _handler via _parse_calibration and 
        trigger callbacks for button_calibrated and imu_calibrated sensors.
        """
        await self.write_command(struct.pack("BBB", 0xFE, 0x55, 0xAA), False)
        await sleep(0.5)
        await self.write_command(struct.pack("B", 0xFC), False)
        await sleep(1.5)
        await self.write_command(struct.pack("BBB", 0xFE, 0x55, 0xAA), False)
        await sleep(0.5)
        await self.write_command(struct.pack("B", 0xFB), False)

    async def get_wand_address(self) -> str:
        """Get wand BLE address."""
        data = await self.write_command(struct.pack("B", 0x08), True)
        if len(data) < 7:
            return ""
        mac_le = data[1:7]
        mac_be = mac_le[::-1]
        return ":".join(f"{b:02X}" for b in mac_be)

    async def get_box_address(self) -> str:
        """Get box BLE address."""
        data = await self.write_command(struct.pack("B", 0x09), True)
        if len(data) < 7:
            return ""
        mac_le = data[1:7]
        mac_be = mac_le[::-1]
        return ":".join(f"{b:02X}" for b in mac_be)

    async def get_wand_no(self) -> str:
        """Get wand model number."""
        data = await self.write_command(struct.pack("BB", 0x0E, 0x04), True)
        if len(data) < 3:
            return ""
        return data[2:].decode("ascii", errors="ignore")

    async def send_macro(self, macro: Macro) -> None:
        """Send a macro sequence to the wand."""
        await self.write_command(macro.to_bytes(), False)

    async def set_led(self, group: LedGroup, red: int, green: int, blue: int, duration_ms: int = 0) -> None:
        """Set LED color on a specific group."""
        macro = Macro().add_led(group, red, green, blue, duration_ms)
        await self.send_macro(macro)

    async def clear_leds(self) -> None:
        """Clear all LEDs."""
        macro = Macro().add_clear()
        await self.send_macro(macro)

    async def buzz(self, duration_ms: int) -> None:
        """Vibrate the wand."""
        macro = Macro().add_buzz(duration_ms)
        await self.send_macro(macro)