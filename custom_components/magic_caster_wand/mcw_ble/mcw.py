# mcw_ble.py
"""BLE client for Magic Caster Wand communication."""

from __future__ import annotations

import logging
import struct
import asyncio
from asyncio import Event, sleep, wait_for
from typing import Any, Callable, TypeVar

from bleak import BleakClient, BleakError

SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
COMMAND_UUID = "57420002-587e-48a0-974c-544d6163c577"
NOTIFY_UUID = "57420003-587e-48a0-974c-544d6163c577"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Message packet IDs from APK
class MESSAGEIDS:
    FIRMWARE_VERSION_READ = 0x00 
    """FirmwareVersionReadMessage.kt"""
    CHALLENGE = 0x01
    """ChallengeMessage.kt"""
    PAIR_WITH_ME = 0x03
    """PairWithMeMessage.kt"""
    BOX_ADDRESS_READ = 0x09
    """BoxAddressReadMessage.kt"""
    WAND_PRODUCT_INFORMATION_READ = 0x0E
    """WandProductInfoReadMessage.kt"""
    IMUFLAG_SET = 0x30
    """IMUFlagMessage.kt"""
    IMUFLAG_RESET = 0x31
    """IMUFlagMessage.kt"""
    LIGHT_CONTROL_CLEAR_ALL = 0x40
    """LightControlClearAllMessage.kt"""
    LIGHT_CONTROL_SET_LED = 0x42
    """LightControlSetMessage.kt"""
    BUTTON_SET_THRESHOLD = 0xDC
    """ButtonSetThresholdMessage.kt"""
    BUTTON_READ_THRESHOLD = 0xDD
    """ButtonReadThresholdMessage.kt"""
    BUTTON_CALIBRATION_BASELINE = 0xFB
    """ButtonCalibrationBaselineMessage.kt"""
    IMU_CALIBRATION = 0xFC
    """IMUCalibrationMessage.kt"""
    FACTORY_UNLOCK = 0xFE
    """FactoryUnlockMessage.kt"""

# Response packet IDs from APK
class RESPONSEIDS:
    FIRMWARE_VERSION = 0x00
    """FirmwareVersionResponseMessage.kt"""
    CHALLENGE = 0x01
    """ChallengeResponseMessage.kt"""
    PONG = 0x02
    """PongResponseMessage.kt"""
    BOX_ADDRESS = 0x09
    """BoxAddressResponseMessage.kt"""
    BUTTON_PAYLOAD = 0x10
    """ButtonPayloadMessage.kt"""
    WAND_PRODUCT_INFORMATION = 0x0E
    """WandProductInfoResponseMessage.kt"""
    SPELL_CAST = 0x24
    """???"""
    IMU_PAYLOAD = 0x2C
    """IMUPayloadMessage.kt"""
    BUTTON_READ_THRESHOLD = 0xDD
    """ButtonReadThresholdResponseMessage.kt"""
    BUTTON_CALIBRATION_BASELINE = 0xFB
    """ButtonCalibrationBaselineResponseMessage.kt"""
    IMU_CALIBRATION = 0xFC
    """IMUCalibrationResponseMessage.kt"""

MESSAGE_TO_RESPONSE_MAP: dict[int, int] = {
    MESSAGEIDS.BOX_ADDRESS_READ: RESPONSEIDS.BOX_ADDRESS,
    MESSAGEIDS.BUTTON_CALIBRATION_BASELINE: RESPONSEIDS.BUTTON_CALIBRATION_BASELINE,
    MESSAGEIDS.CHALLENGE: RESPONSEIDS.CHALLENGE,
    MESSAGEIDS.FIRMWARE_VERSION_READ: RESPONSEIDS.FIRMWARE_VERSION,
    MESSAGEIDS.IMU_CALIBRATION: RESPONSEIDS.IMU_CALIBRATION,
    MESSAGEIDS.WAND_PRODUCT_INFORMATION_READ: RESPONSEIDS.WAND_PRODUCT_INFORMATION,
}

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
        self.callback_spell: Callable[[str], None] | None = None
        self.callback_battery: Callable[[float], None] | None = None
        self.callback_buttons: Callable[[dict[str, bool]], None] | None = None
        self.callback_calibration: Callable[[dict[str, bool]], None] | None = None
        self.lock = asyncio.Lock()

        self._box_address: str | None = None
        self._waiting_cmd_event: Event = Event()
        self._waiting_for_msg_id: int | None = None
        self._wand_challenge: int | None = None
        self._wand_device_id: str | None = None
        self._wand_firmware_version: str | None = None
        self._wand_serial_number: str | None = None
        self._wand_sku: str | None = None
        self._wand_type: str | None = None
        
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.client.is_connected

    def register_callback(self, spell_cb: Callable, battery_cb: Callable, buttons_cb: Callable, calibration_cb: Callable) -> None:
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

        if not data or len(data) < 1:
            return

        opcode = data[0]

        try:
            if opcode == RESPONSEIDS.FIRMWARE_VERSION:
                self._parse_firmware_version(data)

            elif opcode == RESPONSEIDS.CHALLENGE:
                self._parse_challenge(data)

            elif opcode == RESPONSEIDS.BOX_ADDRESS:
                self._parse_box_address(data)

            elif opcode == RESPONSEIDS.WAND_PRODUCT_INFORMATION:
                self._parse_wand_information(data)

            elif opcode == RESPONSEIDS.BUTTON_PAYLOAD:
                self._parse_buttons(data)

            elif opcode == RESPONSEIDS.SPELL_CAST:
                self._parse_spell(data)

            elif opcode == RESPONSEIDS.BUTTON_CALIBRATION_BASELINE or opcode == RESPONSEIDS.IMU_CALIBRATION:
                self._parse_calibration(data)

            else:
                _LOGGER.debug("Unknown opcode: 0x%02X, length=%d", opcode, len(data))

        except Exception as e:
            _LOGGER.error("Error in message handler for opcode 0x%02X: %s", opcode, e)
            _LOGGER.debug("Stack trace:", exc_info=True)

        # Signal waiting command if this message matches expected response
        if self._waiting_for_msg_id is not None and opcode == self._waiting_for_msg_id:
            _LOGGER.debug("Received expected response 0x%02X, signaling caller", opcode)
            self._waiting_cmd_event.set()
            self._waiting_for_msg_id = None

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

    async def write_command(self, packet: bytes, timeout: float = 5.0) -> None:
        """Write command and optionally wait for response."""
        async with self.lock:
            max_retries = 3

            # Extract command ID from packet (first byte)
            cmd_id = packet[0] if len(packet) > 0 else None
            if cmd_id is None:
                raise ValueError("Empty packet")

            # Check if this command expects a response
            expected_msg_id: int | None = MESSAGE_TO_RESPONSE_MAP.get(cmd_id)
            expects_response: bool = expected_msg_id is not None

            for attempt in range(1, max_retries + 1):
                try:
                    if expects_response:
                        _LOGGER.debug("Sending command 0x%02X, expecting response 0x%02X", cmd_id, expected_msg_id)
                        self._waiting_cmd_event.clear()
                        self._waiting_for_msg_id = expected_msg_id
                    else:
                        _LOGGER.debug("Sending command 0x%02X (no response expected)", cmd_id)

                    await self.write(COMMAND_UUID, packet, False)

                    if expects_response:
                        await wait_for(self._waiting_cmd_event.wait(), timeout)
                        _LOGGER.debug("Command 0x%02X completed successfully", cmd_id)
                    
                    return
                except Exception as err:
                    if attempt < max_retries:
                        _LOGGER.warning(
                            "Write retry (attempt %d/%d): %s", attempt, max_retries, err
                        )
                        await sleep(0.5)
                    else:
                        raise

    async def init_wand(self) -> None:
        """Initialize the wand."""
        commands = [
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x00, 0x05),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x01, 0x05),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x02, 0x05),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x03, 0x05),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x04, 0x08),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x05, 0x08),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x06, 0x08),
            struct.pack("BBB", MESSAGEIDS.BUTTON_SET_THRESHOLD, 0x07, 0x08),
        ]
        for cmd in commands:
            await self.write_command(cmd)

    async def challenge(self) -> int:
        """Send keep-alive command."""
        await self.write_command(struct.pack("B", MESSAGEIDS.CHALLENGE))
        return self._wand_challenge or 0
    
    async def calibration(self) -> None:
        """Send calibration commands.
        
        Sends FE 55 AA to start calibration, then FB and FC commands.
        Responses are parsed in _handler via _parse_calibration and 
        trigger callbacks for button_calibrated and imu_calibrated sensors.
        """
        await self.write_command(struct.pack("BBB", MESSAGEIDS.FACTORY_UNLOCK, 0x55, 0xAA))
        await sleep(0.5)
        await self.write_command(struct.pack("B", MESSAGEIDS.IMU_CALIBRATION))
        await sleep(1.5)
        await self.write_command(struct.pack("BBB", MESSAGEIDS.FACTORY_UNLOCK, 0x55, 0xAA))
        await sleep(0.5)
        await self.write_command(struct.pack("B", MESSAGEIDS.BUTTON_CALIBRATION_BASELINE))

    async def get_box_address(self) -> str:
        """Get box BLE address."""
        if self._box_address is None:
            await self.write_command(struct.pack("B", MESSAGEIDS.BOX_ADDRESS_READ))
        return self._box_address or ""

    async def get_wand_device_id(self) -> str:
        """Get wand device ID."""
        if self._wand_device_id is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.WAND_PRODUCT_INFORMATION_READ, 0x04))
        return self._wand_device_id or ""

    async def get_wand_firmware_version(self) -> str:
        """Get wand firmware version."""
        if self._wand_firmware_version is None:
            await self.write_command(struct.pack("B", MESSAGEIDS.FIRMWARE_VERSION_READ))
        return self._wand_firmware_version or ""

    async def get_wand_serial_number(self) -> str:
        """Get wand serial number."""
        if self._wand_serial_number is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.WAND_PRODUCT_INFORMATION_READ, 0x01))
        return self._wand_serial_number or ""
    
    async def get_wand_sku(self) -> str:
        """Get wand SKU."""
        if self._wand_sku is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.WAND_PRODUCT_INFORMATION_READ, 0x02))
        return self._wand_sku or ""

    async def get_wand_type(self) -> str:
        """Get wand type from the device ID."""
        if self._wand_type is None:
            self._wand_type = self._wand_device_id_to_type(await self.get_wand_device_id())
        return self._wand_type or ""

    async def send_macro(self, macro: Macro) -> None:
        """Send a macro sequence to the wand."""
        await self.write_command(macro.to_bytes())

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

    def _parse_box_address(self, data: bytearray) -> None:
        """Parse box address (ID 0x09)"""
        if len(data) < 7:
            return
        try:
            mac_le = data[1:7]
            mac_be = mac_le[::-1]
            self._box_address = ":".join(f"{b:02X}" for b in mac_be)
            _LOGGER.debug("Box address: %s", self._box_address)
        except Exception as e:
            _LOGGER.error("Error parsing box address: %s", e)

    def _parse_challenge(self, data: bytearray) -> None:
        """Parse challenge response (ID 0x01)"""
        if len(data) == 3:
            self._wand_challenge = struct.unpack('<H', data[1:3])[0]

    def _parse_firmware_version(self, data: bytearray) -> None:
        """Parse firmware version message (ID 0x00)

        Response format: [0x00] [version_bytes...]
        """
        if len(data) < 2:
            return
        try:
            # Skip first byte (opcode)
            version_bytes = data[1:]

            # Convert bytes to dotted version string (decimal values)
            # e.g., [0, 3] -> "0.3", [1, 2, 3] -> "1.2.3"
            version = ".".join(str(b) for b in version_bytes)

            _LOGGER.debug("Firmware version: %s", version)
            self._wand_firmware_version = version
        except Exception as e:
            _LOGGER.error("Error parsing firmware version: %s", e)

    def _parse_wand_information(self, data: bytearray) -> None:
        """Parse wand information message (ID 0x0E)"""
        if len(data) < 3:
            return
        try:
            info_type = data[1]

            if info_type == 0x01:
                if len(data) >= 6:
                    serial = struct.unpack('<I', data[2:6])[0]
                    self._wand_serial_number = str(serial)
                    _LOGGER.debug("Wand serial number: %s", self._wand_serial_number)
            elif info_type == 0x02:
                self._wand_sku = data[2:].decode('ascii', errors='ignore').strip('\x00')
                _LOGGER.debug("Wand SKU: %s", self._wand_sku)
            elif info_type == 0x04:
                self._wand_device_id = data[2:].decode('ascii', errors='ignore').strip('\x00')
                _LOGGER.debug("Wand device id: %s", self._wand_device_id)
        except Exception as e:
            _LOGGER.error("Error parsing wand information: %s", e)

    def _wand_device_id_to_type(self, device_id: str) -> str:
        """Extract wand type from device ID string

        Device ID format: [prefix][type_suffix][variant_char]
        Example: "WBMC22G1SHNW" -> "HN" -> "HONOURABLE"

        Based on Android WandDeviceInfoFactory.kt

        Args:
            device_id: Device ID string from product info (e.g., "WBMC22G1SHNW")

        Returns:
            Wand type string (e.g., "HONOURABLE", "HEROIC", etc.)
        """
        if len(device_id) < 3:
            return "UNKNOWN"

        # Extract type suffix: drop last char, take last 2
        # Example: "WBMC22G1SHNW" -> "WBMC22G1SHN" -> "HN"
        type_suffix = device_id[:-1][-2:]

        # Map suffix to wand type (from WandType.kt)
        type_mapping = {
            "DF": "DEFIANT",
            "LY": "LOYAL",
            "HR": "HEROIC",
            "HN": "HONOURABLE",
            "AV": "ADVENTUROUS",
            "WS": "WISE",
        }

        return type_mapping.get(type_suffix, "UNKNOWN")
