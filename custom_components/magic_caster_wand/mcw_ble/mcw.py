# mcw_ble.py

from __future__ import annotations
from enum import Enum
import logging
import struct
import traceback
from typing import Any, Callable, TypeVar
from asyncio import Event, wait_for, sleep
from bleak import BleakClient, BleakError

SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
COMMAND_UUID = "57420002-587e-48a0-974c-544d6163c577"
NOTIFY_UUID = "57420003-587e-48a0-974c-544d6163c577"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

_LOGGER = logging.getLogger(__name__)

# Command IDs (based on Android implementation)
CMD_ID_GET_FIRMWARE_VERSION = 0x00
CMD_ID_KEEP_ALIVE = 0x01
CMD_ID_GET_BOX_ADDRESS = 0x09
CMD_ID_GET_WAND_INFORMATION = 0x0E
CMD_ID_IMU_STREAMING_START = 0x30
CMD_ID_IMU_STREAMING_STOP = 0x31
CMD_ID_LIGHT_CONTROL_CLEAR_ALL = 0x40
CMD_ID_LIGHT_CONTROL_SET = 0x42
CMD_ID_SET_BUTTON_THRESHOLD = 0xDC
CMD_ID_CALIBRATE_BUTTON_BASELINE = 0xFB
CMD_ID_RESET = 0xFF

# Macro Command IDs (based on Android implementation)
MACRO_CMD_ID_VIBRATE = 0x50

# Message IDs (based on Android implementation)
MSG_ID_FIRMWARE_VERSION = 0x00
MSG_ID_BOX_ADDRESS = 0x09
MSG_ID_WAND_INFORMATION = 0x0E
MSG_ID_BUTTON_PAYLOAD = 0x10
MSG_ID_SPELL_CAST = 0x24
MSG_ID_IMU_PAYLOAD = 0x2C
MSG_ID_BUTTON_THRESHOLD_RESPONSE = 0xDD
MSG_ID_CALIBRATE_BASELINE_RESPONSE = 0xFB
MSG_ID_IMU_CALIBRATION_RESPONSE = 0xFC

# Mapping from command ID to expected response message ID
# NOTE: The cmd and msg ids generally match, but this is safer
CMD_TO_MSG_MAP = {
    CMD_ID_CALIBRATE_BUTTON_BASELINE: MSG_ID_CALIBRATE_BASELINE_RESPONSE,
    CMD_ID_GET_BOX_ADDRESS: MSG_ID_BOX_ADDRESS,
    CMD_ID_GET_FIRMWARE_VERSION: MSG_ID_FIRMWARE_VERSION,
    CMD_ID_GET_WAND_INFORMATION: MSG_ID_WAND_INFORMATION,
}

# Sensor scale factors (from Android IMUSample.java)
ACCELEROMETER_SCALE = 0.00048828125
GYROSCOPE_SCALE = 0.0010908308

# Exception definitions
class BleakCharacteristicMissing(BleakError):
    """Characteristic Missing"""

class BleakServiceMissing(BleakError):
    """Service Missing"""

class ButtonState:
    """Represents the capacitive button touch state"""

    def __init__(self, button_byte: int):
        # Convert byte to 8-bit boolean array
        self.bits = [(button_byte & (128 >> i)) != 0 for i in range(8)]

        # Extract individual pad states (last 4 bits)
        self.pad1 = bool(self.bits[4]) if len(self.bits) > 4 else False
        self.pad2 = bool(self.bits[5]) if len(self.bits) > 5 else False
        self.pad3 = bool(self.bits[6]) if len(self.bits) > 6 else False
        self.pad4 = bool(self.bits[7]) if len(self.bits) > 7 else False

        # Full touch detection (all 4 pads touched)
        self.full_touch = self.pad1 and self.pad2 and self.pad3 and self.pad4

    def __repr__(self):
        return f"ButtonState(full={self.full_touch}, pads=[{self.pad1}, {self.pad2}, {self.pad3}, {self.pad4}])"

class IMUSample:
    """Represents a single IMU sensor sample with gyroscope and accelerometer data"""

    def __init__(self, gyro_x: int, gyro_y: int, gyro_z: int, accel_x: int, accel_y: int, accel_z: int):
        self.gyro_x = gyro_x
        self.gyro_y = gyro_y
        self.gyro_z = gyro_z
        self.accel_x = accel_x
        self.accel_y = accel_y
        self.accel_z = accel_z

    def get_scaled_accel(self) -> tuple[float, float, float]:
        """Returns accelerometer data scaled to G-forces"""
        return (
            self.accel_x * ACCELEROMETER_SCALE,
            self.accel_y * ACCELEROMETER_SCALE,
            self.accel_z * ACCELEROMETER_SCALE
        )

    def get_scaled_gyro(self) -> tuple[float, float, float]:
        """Returns gyroscope data scaled to rad/s"""
        return (
            self.gyro_x * GYROSCOPE_SCALE,
            self.gyro_y * GYROSCOPE_SCALE,
            self.gyro_z * GYROSCOPE_SCALE
        )

    def __repr__(self):
        return (f"IMUSample(gyro=({self.gyro_x}, {self.gyro_y}, {self.gyro_z}), "
                f"accel=({self.accel_x}, {self.accel_y}, {self.accel_z}))")

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

def disconnect_on_missing_services(func: WrapFuncType) -> WrapFuncType:
    """Missing services"""
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except (BleakServiceMissing, BleakCharacteristicMissing):
            try:
                if self._client.is_connected:
                    await self._client.clear_cache()
                    await self._client.disconnect()
            except Exception:
                pass
            raise
    return wrapper  # type: ignore

class McwClient:

    def __init__(
        self,
        client: BleakClient,
    ) -> None:
        self.callback_battery = None
        self.callback_button = None
        self.callback_imu = None
        self.callback_spell = None

        self._client = client
        self._box_address = None
        self._waiting_cmd_event: Event = Event()
        self._waiting_for_msg_id: int | None = None
        self._wand_address = None
        self._wand_device_id = None
        self._wand_firmware_version = None
        self._wand_serial_number = None
        self._wand_sku = None
        self._wand_type = None

    def is_connected(self) -> bool:
        return self._client.is_connected
    
    def register_callbacks(self, spell_cb, battery_cb, button_cb=None, imu_cb=None) -> None:
        """Register callbacks for different data types"""
        self.callback_battery = battery_cb
        self.callback_button = button_cb
        self.callback_imu = imu_cb
        self.callback_spell = spell_cb

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        await self._client.start_notify(NOTIFY_UUID, self._handler)
        await self._client.start_notify(BATTERY_UUID, self._handlerBattery)
        await sleep(1.0)

    @disconnect_on_missing_services
    async def stop_notify(self) -> None:
        await self._client.stop_notify(NOTIFY_UUID)
        await self._client.stop_notify(BATTERY_UUID)

    @disconnect_on_missing_services
    async def write(self, uuid: str, data: bytes, response = False) -> None:
        _LOGGER.debug("Write UUID=%s data=%s", uuid, data.hex())
        chunk = len(data)
        for i in range(0, len(data), chunk):
            await self._client.write_gatt_char(uuid, data[i : i + chunk], response)
            #await sleep(0.05)

    def _handlerBattery(self, _: Any, data: bytearray) -> None:
        _LOGGER.debug("Battery Received: %s", data.hex())
        battery = int.from_bytes(data, byteorder="little")
        if self.callback_battery:
            self.callback_battery(battery)

    def _handler(self, _: Any, data: bytearray) -> None:
        """Main message handler - routes messages based on opcode"""
        _LOGGER.debug("Received: %s", data.hex())

        if not data or len(data) < 1:
            return

        opcode = data[0]

        try:
            # Route messages based on opcode (Android WandCharacteristicManager.decode())
            if opcode == MSG_ID_FIRMWARE_VERSION:
                self._parse_firmware_version(data)

            elif opcode == MSG_ID_BOX_ADDRESS:
                self._parse_box_address(data)

            elif opcode == MSG_ID_WAND_INFORMATION:
                self._parse_wand_information(data)

            elif opcode == MSG_ID_BUTTON_PAYLOAD:
                self._parse_button_payload(data)

            elif opcode == MSG_ID_SPELL_CAST:
                if len(data) < 5: 
                    return
                spell_len = data[3]
                raw_name = data[4 : 4 + spell_len]
                spell_name = raw_name.decode('utf-8', errors='ignore').strip()
                spell_name = spell_name.replace('\x00', '').replace('_', ' ')
                if not spell_name:
                    return
                _LOGGER.debug("spell: %s", spell_name)
                _LOGGER.debug("callback: %s", self.callback_spell)
                if self.callback_spell:
                    self.callback_spell(spell_name)   

            elif opcode == MSG_ID_IMU_PAYLOAD:
                self._parse_imu_payload(data)

            elif opcode == MSG_ID_BUTTON_THRESHOLD_RESPONSE:
                if len(data) >= 3:
                    index = data[1]
                    threshold = data[2]
                    _LOGGER.debug("Button threshold response: index=%d, threshold=%d",
                                index, threshold)

            elif opcode == MSG_ID_CALIBRATE_BASELINE_RESPONSE:
                _LOGGER.debug("Calibrate baseline response")

            elif opcode == MSG_ID_IMU_CALIBRATION_RESPONSE:
                _LOGGER.debug("IMU calibration response")

            else:
                _LOGGER.debug("Unknown opcode: 0x%02X, length=%d", opcode, len(data))

        except Exception as e:
            _LOGGER.error("Error in message handler for opcode 0x%02X: %s", opcode, e)
            _LOGGER.debug("Stack trace:", exc_info=True)

        # Signal waiting command if this message matches expected response
        if self._waiting_for_msg_id is not None and opcode == self._waiting_for_msg_id:
            _LOGGER.debug("Received expected response 0x%02X", opcode)
            self._waiting_cmd_event.set()

    async def write_command(self, packet: bytes, timeout: float = 5.0):
        """Write a command to the wand.

        Commands that have a mapping in CMD_TO_MSG_MAP will automatically wait for
        their response. Commands without a mapping are fire-and-forget.
        """
        last_exception = None
        max_retries = 3

        # Extract command ID from packet (first byte)
        cmd_id = packet[0] if len(packet) > 0 else None
        if cmd_id is None:
            raise ValueError("Empty packet")

        # Check if this command expects a response
        expected_msg_id = CMD_TO_MSG_MAP.get(cmd_id)
        expects_response = expected_msg_id is not None

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
                    # Wait for response
                    await wait_for(self._waiting_cmd_event.wait(), timeout)
                    _LOGGER.debug("Command 0x%02X completed successfully", cmd_id)

                return  # Success, exit retry loop

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    _LOGGER.warning(f"Write retry (attempt {attempt}/{max_retries})")
                    await sleep(0.5)
                    continue
                raise last_exception
            finally:
                self._waiting_for_msg_id = None

    async def calibrate_button_baseline(self) -> None:
        """Calibrate button baseline (capacitive touch sensors)

        Recalibrates the capacitive touch sensor baseline to determine what
        the wand considers the "not touched" state. This helps improve touch
        sensitivity and accuracy.

        Response will come via MSG_ID_CALIBRATE_BASELINE_RESPONSE (0xFB)
        """
        _LOGGER.debug("Sending baseline calibration command")
        await sleep(1.0)
        await self._factory_unlock()
        await self.write_command(struct.pack('B', CMD_ID_CALIBRATE_BUTTON_BASELINE))
        await sleep(1.0)
        await self.vibrate(200)

    async def get_box_address(self) -> str:
        """Get companion box MAC address"""
        if self._box_address is None:
            await self.write_command(struct.pack('B', CMD_ID_GET_BOX_ADDRESS))
        return self._box_address or ""

    async def get_wand_device_id(self) -> str:
        """Get wand device ID"""
        if self._wand_device_id is None:
            await self.write_command(struct.pack('BB', CMD_ID_GET_WAND_INFORMATION, 0x04))
        return self._wand_device_id or ""

    async def get_wand_firmware_version(self) -> str:
        """Request firmware version"""
        if self._wand_firmware_version is None:
            await self.write_command(struct.pack('B', CMD_ID_GET_FIRMWARE_VERSION))
        return self._wand_firmware_version or ""

    async def get_wand_serial_number(self) -> str:
        """Get wand serial number"""
        if self._wand_serial_number is None:
            await self.write_command(struct.pack('BB', CMD_ID_GET_WAND_INFORMATION, 0x01))
        return self._wand_serial_number or ""

    async def get_wand_sku(self) -> str:
        """Get wand SKU"""
        if self._wand_sku is None:
            await self.write_command(struct.pack('BB', CMD_ID_GET_WAND_INFORMATION, 0x02))
        return self._wand_sku or ""

    async def get_wand_type(self) -> str:
        """Get wand model type"""
        if self._wand_type is None:
            self._wand_type = self._wand_device_id_to_type(await self.get_wand_device_id())
        return self._wand_type or ""

    async def imu_streaming_start(self) -> None:
        """Start IMU data streaming"""
        _LOGGER.debug("Starting IMU streaming")
        await self.write_command(struct.pack('BBB', CMD_ID_IMU_STREAMING_START, 0x00, 0x01), False)

    async def imu_streaming_stop(self) -> None:
        """Stop IMU data streaming (Android: sendIMUStop)"""
        _LOGGER.debug("Stopping IMU streaming")
        await self.write_command(struct.pack('B', CMD_ID_IMU_STREAMING_STOP), False)

    async def init_wand(self):
        """Initialize wand with default configuration

        TODO: Implement different configurations based on wand type
            HEROIC / HONOURABLE:
                Min: 5, 5, 5, 5
                Max: 8, 8, 8, 8
            LOYAL:
                Min: 7, 7, 10, 10
                Max: 10, 10, 13, 13
            DEFIANT:
                Min: 7, 7, 7, 7
                Max: 10, 10, 10, 10
        """
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x00, 0x05))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x01, 0x05))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x02, 0x05))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x03, 0x05))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x04, 0x08))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x05, 0x08))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x06, 0x08))
        await self.write_command(struct.pack('BBB', CMD_ID_SET_BUTTON_THRESHOLD, 0x07, 0x08))

    async def keep_alive(self) -> bytes:
        """Send keep-alive packet"""
        await self.write_command(struct.pack('B', CMD_ID_KEEP_ALIVE))

    async def led_on(self, r: int, g: int, b: int) -> None:
        """Set wand LED color

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)

        Based on Android: LightControlSetMessage (opcode 0x42 'B')
        Format: [0x42] [?] [r] [g] [b]
        """
        _LOGGER.debug("Setting LED color to R=%d G=%d B=%d", r, g, b)
        await self.write_command(struct.pack('BBBBB', CMD_ID_LIGHT_CONTROL_SET, 3, r, g, b))

    async def led_off(self) -> None:
        """Turn off wand LED

        Based on Android: LightControlClearAllMessage (opcode 0x40 '@')
        Format: [0x40]
        """
        _LOGGER.debug("Turning off LED")
        await self.write_command(struct.pack('B', CMD_ID_LIGHT_CONTROL_CLEAR_ALL))

    async def reset_wand(self) -> None:
        """Reset wand to default configuration

        WARNING: This may disconnect the wand. Reconnection required.
        """
        _LOGGER.warning("Resetting wand to defaults")
        await self.write_command(struct.pack('B', CMD_ID_RESET))

    async def vibrate(self, duration_ms: int = 100) -> None:
        """Trigger wand vibration (haptic feedback)

        Args:
            duration_ms: Vibration duration in milliseconds (max 32767)

        Based on Android: MacroHapBuzzMessage (opcode 0x50 'P')
        Format: [0x68] [0x50] [duration_low] [duration_high]
        """
        if duration_ms > 32767:
            duration_ms = 32767

        _LOGGER.debug("Sending vibrate command (%dms)", duration_ms)

        # Convert to little-endian short
        duration_bytes = struct.pack('<H', duration_ms)

        # Build macro: buzz command (0x50) + duration
        macro = struct.pack('BBB', MACRO_CMD_ID_VIBRATE, duration_bytes[1], duration_bytes[0])

        await self._send_macro(macro)

    async def _factory_unlock(self) -> None:
        """Unlock factory/calibration mode

        This command is sent before calibration operations to enable factory mode.

        Based on Android code: WandManager.factoryUnlockRequest()
        Sends: {0xFE, 0x55, 0xAA}
        """
        _LOGGER.debug("Sending factory unlock command")
        await self.write_command(struct.pack('BBB', 0xFE, 0x55, 0xAA))


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

    def _parse_button_payload(self, data: bytearray) -> None:
        """Parse button state message (ID 0x10)"""
        if len(data) < 2:
            _LOGGER.warning("Invalid button payload length: %d", len(data))
            return

        button_state = ButtonState(data[1])
        _LOGGER.debug("Button state: %s", button_state)

        if self.callback_button:
            self.callback_button({
                'full_touch': button_state.full_touch,
                'pad1': button_state.pad1,
                'pad2': button_state.pad2,
                'pad3': button_state.pad3,
                'pad4': button_state.pad4,
            })

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

    def _parse_imu_payload(self, data: bytearray) -> None:
        """Parse IMU data message (ID 0x2C)

        Based on Android IMUPayloadMessage.kt:
        - Byte 0: Message ID (0x2C)
        - Bytes 1-2: Start index (little-endian short)
        - Byte 3: Sample count
        - Bytes 4+: Sample data (12 bytes per sample)

        Each sample contains 6 shorts (little-endian):
        - gyroX, gyroY, gyroZ, accelX, accelY, accelZ
        """
        if len(data) < 4:
            _LOGGER.warning("Invalid IMU payload length: %d", len(data))
            return

        # Extract header
        sample_count = data[3]
        expected_length = 4 + (sample_count * 12)

        if len(data) < expected_length:
            _LOGGER.warning("IMU payload too short. Expected %d, got %d",
                          expected_length, len(data))
            return

        # Check if payload length is valid (should be divisible by 6 shorts = 12 bytes)
        payload_length = len(data) - 4
        if payload_length % 12 != 0:
            _LOGGER.warning("IMU payload length not divisible by 12: %d", payload_length)
            return

        samples = []
        offset = 4

        for i in range(sample_count):
            try:
                # Parse 6 shorts (little-endian) - 12 bytes total
                gyro_x = struct.unpack_from('<h', data, offset)[0]
                gyro_y = struct.unpack_from('<h', data, offset+2)[0]
                gyro_z = struct.unpack_from('<h', data, offset+4)[0]
                accel_x = struct.unpack_from('<h', data, offset+6)[0]
                accel_y = struct.unpack_from('<h', data, offset+8)[0]
                accel_z = struct.unpack_from('<h', data, offset+10)[0]

                sample = IMUSample(gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z)
                samples.append(sample)

                offset += 12
            except Exception as e:
                _LOGGER.error("Error parsing IMU sample %d: %s", i, e)
                break

        if samples:
            _LOGGER.debug("Parsed %d IMU samples", len(samples))
            if self.callback_imu:
                # Send scaled data
                imu_data = []
                for sample in samples:
                    accel = sample.get_scaled_accel()
                    gyro = sample.get_scaled_gyro()
                    imu_data.append({
                        'accel_x': accel[0],
                        'accel_y': accel[1],
                        'accel_z': accel[2],
                        'gyro_x': gyro[0],
                        'gyro_y': gyro[1],
                        'gyro_z': gyro[2],
                    })
                self.callback_imu(imu_data)

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

    async def _send_macro(self, macro_bytes: bytes) -> None:
        """Send a raw macro command to the wand

        Args:
            macro_bytes: Raw macro payload (without the 'h' prefix)
        """
        # Macro messages are prefixed with 0x68 ('h')
        payload = b'\x68' + macro_bytes
        await self.write_command(payload, False)

    def _wand_device_id_to_type(self, device_id: str) -> str:
        """Extract wand type from device ID string

        Device ID format: [prefix][type_suffix][variant_char]
        Example: "WBMC22G1SHNW" -> "HN" -> "HONOURABLE"

        Based on Android WandDeviceInfoFactory.java:
        - Drop last character
        - Take last 2 characters
        - Map to WandType enum

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

        # Map suffix to wand type (from WandType.java)
        type_mapping = {
            "DF": "DEFIANT",
            "LY": "LOYAL",
            "HR": "HEROIC",
            "HN": "HONOURABLE",
            "AV": "ADVENTUROUS",
            "WS": "WISE",
        }

        return type_mapping.get(type_suffix, "UNKNOWN")