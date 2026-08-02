    # mcb_ble.py
"""BLE client for Magic Caster Wand Box communication."""

from __future__ import annotations

import logging
import struct
import asyncio
from asyncio import Event, sleep, wait_for
from bleak import BleakClient, BleakError
from .macros import LedGroup, Macro
from typing import Any, Callable, TypeVar

from enum import Enum, IntEnum, auto

SERVICE_UUID = "57420001-587e-48a0-974c-54686f72c577"
COMMAND_UUID = "57420002-587e-48a0-974c-54686f72c577"
NOTIFY_UUID = "57420003-587e-48a0-974c-54686f72c577"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

class LIDSTATE(Enum):
    LID_ON_NO_WAND = auto()
    LID_OFF_NO_WAND = auto()
    LID_ON_WAND = auto()
    LID_OFF_WAND = auto()
    UNKNOWN = auto()

class LIDNOTIFY(IntEnum):
    LID_REMOVED = 0    
    LID_ON = 1


class WANDNOTIFY(IntEnum):
    WAND_REMOVED = 0
    WAND_PLUGGED = 1

class CHARGENOTIFY(IntEnum):
    CHARGE_UNPLUGGED = 0
    CHARGE_PLUGGED = 1

# Message packet IDs from APK
class MESSAGEIDS:
    FIRMWARE_VERSION_READ = 0x00 
    """FirmwareVersionReadMessage.kt"""
    CHALLENGE = 0x01
    """ChallengeMessage.kt"""
    PAIR_WITH_ME = 0x03
    """PairWithMeMessage.kt"""
    WAND_ADDRESS_READ = 0x09
    """Read the address of the wand paired with this box."""
    BOX_PRODUCT_INFORMATION_READ = 0x0E
    """Read this box's own serial number, SKU and device ID."""
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

    LID_STATUS_SEND = 0x10      # Combined lid/wand status request
    LID_NOTIFY_REQUEST = 0x11   # Request lid notifications
    WAND_NOTIFY_REQUEST = 0x12  # Request wand plug/unplug notifications
    CHARGE_NOTIFY_REQUEST = 0x13     

# Response packet IDs from APK
class RESPONSEIDS:
    FIRMWARE_VERSION = 0x00
    """FirmwareVersionResponseMessage.kt"""
    CHALLENGE = 0x01
    """ChallengeResponseMessage.kt"""
    PONG = 0x02
    """PongResponseMessage.kt"""
    WAND_ADDRESS = 0x09
    """Address of the wand paired with this box."""
    BUTTON_PAYLOAD = 0x10
    """ButtonPayloadMessage.kt"""
    BOX_PRODUCT_INFORMATION = 0x0E
    """This box's own serial number, SKU and device ID."""
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

    LID_STATUS = 0x10
    LID_NOTIFY = 0x11
    WAND_NOTIFY = 0x12
    CHARGE_NOTIFY = 0x13    

MESSAGE_TO_RESPONSE_MAP: dict[int, int] = {
    MESSAGEIDS.WAND_ADDRESS_READ: RESPONSEIDS.WAND_ADDRESS,
    MESSAGEIDS.BUTTON_CALIBRATION_BASELINE: RESPONSEIDS.BUTTON_CALIBRATION_BASELINE,
    MESSAGEIDS.CHALLENGE: RESPONSEIDS.CHALLENGE,
    MESSAGEIDS.FIRMWARE_VERSION_READ: RESPONSEIDS.FIRMWARE_VERSION,
    MESSAGEIDS.IMU_CALIBRATION: RESPONSEIDS.IMU_CALIBRATION,
    MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ: RESPONSEIDS.BOX_PRODUCT_INFORMATION,
    MESSAGEIDS.LID_STATUS_SEND: RESPONSEIDS.LID_STATUS,
    MESSAGEIDS.LID_NOTIFY_REQUEST: RESPONSEIDS.LID_NOTIFY,
    MESSAGEIDS.WAND_NOTIFY_REQUEST: RESPONSEIDS.WAND_NOTIFY,
    MESSAGEIDS.CHARGE_NOTIFY_REQUEST: RESPONSEIDS.CHARGE_NOTIFY,    
}

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


class McbClient:
    """BLE client for communicating with Magic Caster Box."""

    def __init__(self, client: BleakClient) -> None:
        """Initialize the client."""
        self.client = client
        self.callback_battery: Callable[[float], None] | None = None
        self.callback_lid: Callable[[LIDNOTIFY], None] | None = None
        self.callback_wand: Callable[[WANDNOTIFY], None] | None = None
        self.callback_charge: Callable[[CHARGENOTIFY], None] | None = None
        self.lock = asyncio.Lock()

        self._wand_address: str | None = None
        self._waiting_cmd_event: Event = Event()
        self._waiting_for_msg_id: int | None = None
        self._box_challenge: int | None = None
        self._box_device_id: str | None = None
        self._box_firmware_version: str | None = None
        self._box_serial_number: str | None = None
        self._box_sku: str | None = None
        self._box_type: str | None = None
        
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.client.is_connected

    def register_callback(
            self,
            battery_cb: Callable[[float], None],
            lid_cb: Callable[[LIDNOTIFY], None],
            wand_cb: Callable[[WANDNOTIFY], None],
            charge_cb: Callable[[CHARGENOTIFY], None]
    ) -> None:
        """Register callbacks for spell, battery, button, and calibration notifications."""
        self.callback_battery = battery_cb

        self.callback_lid = lid_cb
        self.callback_wand = wand_cb
        self.callback_charge = charge_cb        

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        """Start receiving notifications."""
        await self.client.start_notify(NOTIFY_UUID, self._handler)
        await self.client.start_notify(BATTERY_UUID, self._handler_battery)
        await sleep(1.0)

        try:
            # Query initial battery level
            battery_data = await self.client.read_gatt_char(BATTERY_UUID)
            self._handler_battery(None, bytearray(battery_data))
            await self.request_box_notifications()
            await self.request_charge_notifications()
            await self.request_lid_notifications()
            # Lid/wand changes only arrive as notifications, so ask for the
            # current state once to seed the entities on connect.
            await self.request_lid_status()

        except Exception as err:
            _LOGGER.warning("Error during initial box query: %s", err)

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

            elif opcode == RESPONSEIDS.WAND_ADDRESS:
                self._parse_wand_address(data)

            elif opcode == RESPONSEIDS.BOX_PRODUCT_INFORMATION:
                self._parse_box_information(data)

            elif opcode == RESPONSEIDS.LID_STATUS:
                self._parse_lid_status(data)

            elif opcode == RESPONSEIDS.LID_NOTIFY:
                self._parse_lid_notify(data)

            elif opcode == RESPONSEIDS.WAND_NOTIFY:
                self._parse_wand_notify(data)

            elif opcode == RESPONSEIDS.CHARGE_NOTIFY:
                self._parse_charge_notify(data)

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

    async def request_lid_status(self):
        await self.write_command(struct.pack("B", MESSAGEIDS.LID_STATUS_SEND))

    async def request_lid_notifications(self):
        await self.write_command(struct.pack("B", MESSAGEIDS.LID_NOTIFY_REQUEST))

    async def request_box_notifications(self):
        await self.write_command(struct.pack("B", MESSAGEIDS.WAND_NOTIFY_REQUEST))

    async def request_charge_notifications(self):
        await self.write_command(struct.pack("B", MESSAGEIDS.CHARGE_NOTIFY_REQUEST))

    async def get_wand_address(self) -> str:
        """Get the BLE address of the wand paired with this box."""
        if self._wand_address is None:
            await self.write_command(struct.pack("B", MESSAGEIDS.WAND_ADDRESS_READ))
        return self._wand_address or ""

    async def get_box_device_id(self) -> str:
        """Get box device ID."""
        if self._box_device_id is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ, 0x04))
        return self._box_device_id or ""

    async def get_box_firmware_version(self) -> str:
        """Get box firmware version."""
        if self._box_firmware_version is None:
            await self.write_command(struct.pack("B", MESSAGEIDS.FIRMWARE_VERSION_READ))
        return self._box_firmware_version or ""

    async def get_box_serial_number(self) -> str:
        """Get box serial number."""
        if self._box_serial_number is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ, 0x01))
        return self._box_serial_number or ""
    
    async def get_box_sku(self) -> str:
        """Get box SKU."""
        if self._box_sku is None:
            await self.write_command(struct.pack("BB", MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ, 0x02))
        return self._box_sku or ""

    async def get_box_type(self) -> str:
        """Get box type from the device ID."""
        if self._box_type is None:
            self._box_type = self._box_device_id_to_type(await self.get_box_device_id())
        return self._box_type or ""

    async def led_on(self, group: LedGroup, r: int, g: int, b: int) -> None:
        """Set box LED color"""
        _LOGGER.debug("Setting LED %s color to R=%d G=%d B=%d", group.name, r, g, b)

        await self.write_command(struct.pack('BBBBB', MESSAGEIDS.LIGHT_CONTROL_SET_LED, int(group), r, g, b))

    async def led_off(self) -> None:
        """Turn off box LED"""
        _LOGGER.debug("Turning off LED")
        await self.write_command(struct.pack('B', MESSAGEIDS.LIGHT_CONTROL_CLEAR_ALL))

    async def send_macro(self, macro: Macro) -> None:
        """Send a macro sequence to the box."""
        await self.write_command(macro.to_bytes())

    async def buzz(self, duration_ms: int) -> None:
        """Vibrate the box."""
        macro = Macro().add_buzz(duration_ms)
        await self.send_macro(macro)

    def _parse_wand_address(self, data: bytearray) -> None:
        """Parse the paired wand's address (ID 0x09)"""
        if len(data) < 7:
            return
        try:
            mac_le = data[1:7]
            mac_be = mac_le[::-1]
            self._wand_address = ":".join(f"{b:02X}" for b in mac_be)
            _LOGGER.debug("Paired wand address: %s", self._wand_address)
        except Exception as e:
            _LOGGER.error("Error parsing wand address: %s", e)

    def _parse_challenge(self, data: bytearray) -> None:
        """Parse challenge response (ID 0x01)"""
        if len(data) == 3:
            self._box_challenge = struct.unpack('<H', data[1:3])[0]

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
            self._box_firmware_version = version
        except Exception as e:
            _LOGGER.error("Error parsing firmware version: %s", e)

    def _parse_box_information(self, data: bytearray) -> None:
        """Parse box information message (ID 0x0E)"""
        if len(data) < 3:
            return
        try:
            info_type = data[1]

            if info_type == 0x01:
                if len(data) >= 6:
                    serial = struct.unpack('<I', data[2:6])[0]
                    self._box_serial_number = str(serial)
                    _LOGGER.debug("Box serial number: %s", self._box_serial_number)
            elif info_type == 0x02:
                self._box_sku = data[2:].decode('ascii', errors='ignore').strip('\x00')
                _LOGGER.debug("Box SKU: %s", self._box_sku)
            elif info_type == 0x04:
                self._box_device_id = data[2:].decode('ascii', errors='ignore').strip('\x00')
                _LOGGER.debug("Box device id: %s", self._box_device_id)
        except Exception as e:
            _LOGGER.error("Error parsing box information: %s", e)

    def _box_device_id_to_type(self, device_id: str) -> str:
        """Extract box type from device ID string

        Device ID format: [prefix][type_suffix][variant_char]
        Example: "WBMC22G1SHNW" -> "HN" -> "HONOURABLE"

        Based on Android WandDeviceInfoFactory.kt

        Args:
            device_id: Device ID string from product info (e.g., "WBMC22G1SHNW")

        Returns:
            Box type string (e.g., "HONOURABLE", "HEROIC", etc.). A box is sold
            matched to a wand, so it shares the wand type taxonomy.
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

    def _parse_lid_status(self, data: bytearray) -> None:
        """Parse the combined lid/wand status response (ID 0x10).

        Payload byte is a bit field: bit 0 = lid removed, bit 1 = wand present.
        This is the only way to learn the current state on connect, since the
        box reports lid/wand changes by notification only.
        """
        if len(data) < 2:
            return

        mapping = {
            0x00: LIDSTATE.LID_ON_NO_WAND,
            0x01: LIDSTATE.LID_OFF_NO_WAND,
            0x02: LIDSTATE.LID_ON_WAND,
            0x03: LIDSTATE.LID_OFF_WAND,
        }

        state = mapping.get(data[1], LIDSTATE.UNKNOWN)
        _LOGGER.debug(f"Lid/Wand combined status: {state.name}")

        if state is LIDSTATE.UNKNOWN:
            return

        lid = LIDNOTIFY.LID_REMOVED if data[1] & 0x01 else LIDNOTIFY.LID_ON
        wand = WANDNOTIFY.WAND_PLUGGED if data[1] & 0x02 else WANDNOTIFY.WAND_REMOVED

        if self.callback_lid:
            self.callback_lid(lid)
        if self.callback_wand:
            self.callback_wand(wand)

    def _parse_lid_notify(self, data: bytearray) -> None:
        if len(data) < 2:
            return

        state = LIDNOTIFY.LID_ON if data[1] == 0x00 else LIDNOTIFY.LID_REMOVED
        _LOGGER.debug(f"Lid notify: {state.name}")

        if self.callback_lid:
            self.callback_lid(state)

    def _parse_wand_notify(self, data: bytearray) -> None:
        if len(data) < 2:
            return

        state = WANDNOTIFY.WAND_REMOVED if data[1] == 0x00 else WANDNOTIFY.WAND_PLUGGED
        _LOGGER.debug(f"Wand notify: {state.name}")

        if self.callback_wand:
            self.callback_wand(state)

    def _parse_charge_notify(self, data: bytearray) -> None:
        if len(data) < 2:
            return

        state = CHARGENOTIFY.CHARGE_UNPLUGGED if data[1] == 0x00 else CHARGENOTIFY.CHARGE_PLUGGED
        _LOGGER.debug(f"Charge notify: {state.name}")

        if self.callback_charge:
            self.callback_charge(state)

