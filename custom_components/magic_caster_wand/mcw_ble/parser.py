"""Parser for Magic Caster Wand BLE devices."""

import asyncio
import dataclasses
import logging
from pathlib import Path

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from .mcw import McwClient, LedGroup, Macro
from .spell_tracker import SpellTracker

_LOGGER = logging.getLogger(__name__)

# Path to the TFLite model for server-side spell detection
_MODEL_PATH = Path(__file__).parent / "model.tflite"

@dataclasses.dataclass
class BLEData:
    """Response data with information about the Magic Caster Wand device."""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    model: str = ""
    serial_number: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )


class McwDevice:
    """Data handler for Magic Caster Wand BLE device."""

    def __init__(self, address: str) -> None:
        """Initialize the device."""
        self.address = address
        self.client: BleakClient | None = None
        self.model: str | None = None
        self._mcw: McwClient | None = None
        self._data = BLEData()
        self._coordinator_spell = None
        self._coordinator_battery = None
        self._coordinator_buttons = None
        self._coordinator_calibration = None

        # Server-side spell tracking
        self._spell_tracker: SpellTracker | None = None
        self._button_all_pressed: bool = False

        # Casting LED configuration
        self._casting_led_color: tuple[int, int, int] = (255, 255, 255)  # Default white

        # Initialize SpellTracker if model file exists
        if _MODEL_PATH.exists():
            _LOGGER.info("Found spell model at %s, enabling server-side spell detection", _MODEL_PATH)
            self._spell_tracker = SpellTracker(str(_MODEL_PATH))
        else:
            _LOGGER.debug("No spell model found at %s, using wand-native spell detection", _MODEL_PATH)

    @property
    def casting_led_color(self) -> tuple[int, int, int]:
        """Return the current casting LED color."""
        return self._casting_led_color

    @casting_led_color.setter
    def casting_led_color(self, color: tuple[int, int, int]) -> None:
        """Set the casting LED color."""
        _LOGGER.debug("Casting LED color set: %s", color)
        self._casting_led_color = color

    @property
    def spell_detection_mode(self) -> str:
        """Return the current spell detection mode."""
        return "Server" if self._spell_tracker is not None else "Wand"

    def register_coordinator(self, cn_spell, cn_battery, cn_buttons, cn_calibration=None) -> None:
        """Register coordinators for spell, battery, button, and calibration updates."""
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery
        self._coordinator_buttons = cn_buttons
        self._coordinator_calibration = cn_calibration

    def _callback_spell(self, data: str) -> None:
        """Handle spell detection callback from wand-native detection."""
        # Ignore native spell detection if using server-side tracking
        if self._spell_tracker is not None:
            return
        if self._coordinator_spell:
            self._coordinator_spell.async_set_updated_data(data)

    def _callback_battery(self, data: float) -> None:
        """Handle battery update callback."""
        if self._coordinator_battery:
            self._coordinator_battery.async_set_updated_data(data)

    def _callback_buttons(self, data: dict[str, bool]) -> None:
        """Handle button state update callback."""
        if self._coordinator_buttons:
            self._coordinator_buttons.async_set_updated_data(data)

        # Handle spell tracking start/stop when using server-side detection
        if self._spell_tracker is not None:
            button_all = data.get("button_all", False)

            # Transition: not pressed -> pressed = start tracking
            if button_all and not self._button_all_pressed:
                _LOGGER.debug("All buttons pressed, starting spell tracking")
                asyncio.create_task(self._turn_on_casting_led())
                self._spell_tracker.start()

            # Transition: pressed -> not pressed = stop tracking and detect spell
            elif not button_all and self._button_all_pressed:
                _LOGGER.debug("Buttons released, stopping spell tracking")
                asyncio.create_task(self._turn_off_casting_led())
                spell_name = self._spell_tracker.stop()
                if spell_name and self._coordinator_spell:
                    _LOGGER.debug("Server-side spell detected: %s", spell_name)
                    self._coordinator_spell.async_set_updated_data(spell_name)

            self._button_all_pressed = button_all

    async def _turn_on_casting_led(self) -> None:
        """Turn on the casting LED with configured color."""
        if self._mcw:
            try:
                r, g, b = self._casting_led_color
                await self._mcw.led_on(LedGroup.TIP, r, g, b)
                _LOGGER.debug("Casting LED turned on with color: (%d, %d, %d)", r, g, b)
            except Exception as err:
                _LOGGER.warning("Failed to turn on casting LED: %s", err)

    async def _turn_off_casting_led(self) -> None:
        """Turn off the casting LED."""
        if self._mcw:
            try:
                await self._mcw.led_off()
                _LOGGER.debug("Casting LED turned off")
            except Exception as err:
                _LOGGER.warning("Failed to turn off casting LED: %s", err)

    def _callback_calibration(self, data: dict[str, bool]) -> None:
        """Handle calibration state update callback."""
        if self._coordinator_calibration:
            self._coordinator_calibration.async_set_updated_data(data)

    def _callback_imu(self, data: list[dict[str, float]]) -> None:
        """Handle IMU data callback for server-side spell tracking."""
        if self._spell_tracker is None:
            return

        for sample in data:
            # Apply axis remapping (same as imuvisualizer.py)
            self._spell_tracker.update(
                ax=sample['accel_y'],
                ay=-sample['accel_x'],
                az=sample['accel_z'],
                gx=sample['gyro_y'],
                gy=-sample['gyro_x'],
                gz=sample['gyro_z'],
            )

    def is_connected(self) -> bool:
        """Check if the device is currently connected."""
        if self.client:
            try:
                return self.client.is_connected
            except Exception:
                pass
        return False

    async def connect(self, ble_device: BLEDevice) -> bool:
        """Connect to the BLE device."""
        if self.is_connected():
            return True

        try:
            self.client = await establish_connection(
                BleakClient, ble_device, ble_device.address
            )

            if not self.client.is_connected:
                return False

            # Update basic device info
            if not self._data.name:
                self._data.name = ble_device.name or "Magic Caster Wand"
            if not self._data.address:
                self._data.address = ble_device.address
            if not self._data.identifier:
                self._data.identifier = ble_device.address.replace(":", "")[-8:]
            self._mcw = McwClient(self.client)
            self._mcw.register_callback(
                self._callback_spell,
                self._callback_battery,
                self._callback_buttons,
                self._callback_calibration,
                self._callback_imu,
            )
            await self._mcw.start_notify()
            if not self.model:
                self.model = await self._mcw.get_wand_device_id()
                await self._mcw.init_wand()

            # Start IMU streaming if using server-side spell detection
            if self._spell_tracker is not None:
                _LOGGER.debug("Starting IMU streaming for server-side spell detection")
                await self._mcw.imu_streaming_start()

            _LOGGER.debug("Connected to Magic Caster Wand: %s, %s", ble_device.address, self.model)
            return True

        except Exception as err:
            _LOGGER.warning("Failed to connect to %s: %s", ble_device.address, err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the BLE device."""
        if self.client:
            try:
                if self.client.is_connected:
                    if self._mcw:
                        # Stop IMU streaming if using server-side spell detection
                        if self._spell_tracker is not None:
                            await self._mcw.imu_streaming_stop()
                        await self._mcw.stop_notify()
                    await self.client.disconnect()
                    _LOGGER.debug("Disconnected from Magic Caster Wand")
            except Exception as err:
                _LOGGER.warning("Error during disconnect: %s", err)
            finally:
                # Reset button tracking state
                self._button_all_pressed = False
                # Reset all button states to OFF on disconnect
                if self._coordinator_buttons:
                    self._coordinator_buttons.async_set_updated_data({
                        "button_1": False,
                        "button_2": False,
                        "button_3": False,
                        "button_4": False,
                    })

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Update device data. Sends keep-alive if connected."""
        if not ble_device:
            if not self._mcw:
                await self.connect(ble_device)
                await self.disconnect()
        # Send keep-alive if connected
        # if self.is_connected() and self._mcw:
        #     try:
        #         await self._mcw.keep_alive()
        #     except Exception as err:
        #         _LOGGER.debug("Keep-alive failed: %s", err)

        # _LOGGER.debug("Updated BLEData: %s", self._data)
        return self._data

    async def send_macro(self, macro: Macro) -> None:
        """Send a macro sequence to the wand."""
        if self.is_connected() and self._mcw:
            await self._mcw.send_macro(macro)

    async def set_led(self, group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> None:
        """Set LED color."""
        if self.is_connected() and self._mcw:
            await self._mcw.set_led(group, r, g, b, duration)

    async def buzz(self, duration: int) -> None:
        """Vibrate the wand."""
        if self.is_connected() and self._mcw:
            await self._mcw.buzz(duration)

    async def clear_leds(self) -> None:
        """Clear all LEDs."""
        if self.is_connected() and self._mcw:
            await self._mcw.clear_leds()

    async def send_calibration(self) -> None:
        """Send calibration packet."""
        if self.is_connected() and self._mcw:
            await self._mcw.calibration()


class McwBluetoothDeviceData(BluetoothData):
    """Bluetooth device data for Magic Caster Wand."""

    # Magic Caster Wand Service UUID (from mcw.py)
    SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
    # Device name prefix
    DEVICE_NAME_PREFIX = "MCW-"

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        self.pending = True

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is a supported Magic Caster Wand."""
        # Check device name starts with "MCW-"
        if not data.name or not data.name.startswith(self.DEVICE_NAME_PREFIX):
            return False

        # Check for Magic Caster Wand Service UUID
        # service_uuids_lower = [uuid.lower() for uuid in data.service_uuids]
        # if self.SERVICE_UUID.lower() not in service_uuids_lower:
        #     return False

        return True
