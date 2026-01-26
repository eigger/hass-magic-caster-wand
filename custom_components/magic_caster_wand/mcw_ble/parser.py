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
from .remote_tensor_spell_detector import RemoteTensorSpellDetector
from .shape_spell_detector import ShapeSpellDetector
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

    def __init__(self, address: str, tflite_url: str = "http://b5e3f765-tflite-server:8000") -> None:
        """Initialize the device."""
        self.address = address
        self.tflite_url = tflite_url
        self.client: BleakClient | None = None
        self.model: str | None = None
        self._mcw: McwClient | None = None
        self._data = BLEData()
        self._coordinator_spell = None
        self._coordinator_battery = None
        self._coordinator_buttons = None
        self._coordinator_calibration = None
        self._coordinator_imu = None
        self._spell_tracker: SpellTracker | None = None
        self._button_all_pressed: bool = False
        self._spell_reset_timeout_task: asyncio.Task[None] | None = None
        self._casting_led_color: tuple[int, int, int] = (0, 0, 255)  # Default color: blue
        self._server_reachable: bool = False
        
        self._remote_detector: RemoteTensorSpellDetector | None = None
        self._shape_detector: ShapeSpellDetector | None = None

        self._init_spell_tracker()

    def _init_spell_tracker(self) -> None:
        """Initialize the spell tracker."""
        try:
            # 1. Setup Remote Detector (if model exists)
            if _MODEL_PATH.exists():
                self._remote_detector = RemoteTensorSpellDetector(
                    model_path=_MODEL_PATH,
                    base_url=self.tflite_url,
                )
            else:
                 _LOGGER.warning("Remote model not found at %s", _MODEL_PATH)

            # 2. Setup Local Shape Detector
            # Check if custom shapes model exists, otherwise use None (built-in memory)
            shape_model_path = Path(__file__).parent / "shapes_model.json"
            model_source = shape_model_path if shape_model_path.exists() else None
            self._shape_detector = ShapeSpellDetector(model_path=model_source)

            # 3. Create SpellTracker
            # Default to Remote if available, else Shape
            initial_detector = self._remote_detector if self._remote_detector else self._shape_detector
            if initial_detector:
                self._spell_tracker = SpellTracker(initial_detector)
                _LOGGER.debug(f"Spell tracker created (Initial: {type(initial_detector).__name__})")
            else:
                _LOGGER.warning("No spell detector could be created!")

        except Exception as err:
            _LOGGER.warning("Failed to create spell detector: %s", err)



    def register_coordinator(self, cn_spell, cn_battery, cn_buttons, cn_calibration=None, cn_imu=None) -> None:
        """Register coordinators for spell, battery, button, and calibration updates."""
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery
        self._coordinator_buttons = cn_buttons
        self._coordinator_calibration = cn_calibration
        self._coordinator_imu = cn_imu

    def _callback_spell(self, data: str) -> None:
        """Handle spell detection callback from wand-native detection."""
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
                asyncio.create_task(self._async_stop_and_detect_spell())

            self._button_all_pressed = button_all

    async def _async_stop_and_detect_spell(self) -> None:
        """Stop spell tracking and detect spell asynchronously."""
        if self._spell_tracker is None:
            return

        spell_name = await self._spell_tracker.stop()
        if spell_name and self._coordinator_spell:
            _LOGGER.debug("Server-side spell detected: %s", spell_name)
            self._coordinator_spell.async_set_updated_data(spell_name)

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
        """Handle IMU data update callback."""
        if self._coordinator_imu:
            self._coordinator_imu.async_set_updated_data(data)

        if self._spell_tracker is not None:
            for sample in data:
                self._spell_tracker.update(
                    ax=sample['accel_y'],
                    ay=-sample['accel_x'],
                    az=sample['accel_z'],
                    gx=sample['gyro_y'],
                    gy=-sample['gyro_x'],
                    gz=sample['gyro_z']
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
                self._callback_imu
            )
            await self._mcw.start_notify()
            if not self.model:
                self.model = await self._mcw.get_wand_device_id()
                await self._mcw.init_wand()

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
                        # Stop IMU streaming before disconnecting
                        try:
                            await self._mcw.imu_streaming_stop()
                        except Exception as imu_err:
                            _LOGGER.debug("Failed to stop IMU streaming during disconnect: %s", imu_err)
                        await self._mcw.stop_notify()
                    await self.client.disconnect()
                    _LOGGER.debug("Disconnected from Magic Caster Wand")
            except Exception as err:
                _LOGGER.warning("Error during disconnect: %s", err)
            finally:
                # Reset all states on disconnect
                if self._coordinator_buttons:
                    self._coordinator_buttons.async_set_updated_data({
                        "button_1": False,
                        "button_2": False,
                        "button_3": False,
                        "button_4": False,
                        "button_all": False,
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

    @property
    def spell_detection_mode(self) -> str:
        """Get the current spell detection mode."""
        if self._spell_tracker is not None:
            if self._spell_tracker.is_active:
                return "Server"
        return "Wand"

    @property
    def server_reachable(self) -> bool:
        """Check if the TFLite server is reachable."""
        return self._server_reachable

    async def buzz(self, duration: int) -> None:
        """Vibrate the wand."""
        if self.is_connected() and self._mcw:
            await self._mcw.buzz(duration)

    async def clear_leds(self) -> None:
        """Clear all LEDs."""
        if self.is_connected() and self._mcw:
            await self._mcw.clear_leds()

    async def send_button_calibration(self) -> None:
        """Send button calibration packet."""
        if self.is_connected() and self._mcw:
            await self._mcw.calibration_button()

    async def send_imu_calibration(self) -> None:
        """Send IMU calibration packet."""
        if self.is_connected() and self._mcw:
            await self._mcw.calibration_imu()

    async def imu_streaming_start(self) -> None:
        """Start IMU streaming."""
        if self.is_connected() and self._mcw:
            await self._mcw.imu_streaming_start()

    async def imu_streaming_stop(self) -> None:
        """Stop IMU streaming."""
        if self.is_connected() and self._mcw:
            await self._mcw.imu_streaming_stop()

    async def async_spell_tracker_init(self) -> None:
        """Initialize spell tracker and detector session with fallback."""
        if self._spell_tracker is None:
            self._init_spell_tracker()

        if self._spell_tracker is None:
            _LOGGER.warning("Spell tracker not created, cannot initialize")
            return

        try:
            # 1. Try Remote First
            detector_ok = False
            
            if self._remote_detector:
                try:
                    is_reachable = await self._remote_detector.check_connectivity()
                    if is_reachable:
                        await self._remote_detector.async_init()
                        # Switch to Remote
                        self._spell_tracker._detector = self._remote_detector 
                        self._server_reachable = True
                        detector_ok = True
                        _LOGGER.debug(f"Using Remote Spell Detector (Server: {self._remote_detector._base_url})")
                    else:
                         _LOGGER.warning(f"Remote server {self._remote_detector._base_url} unreachable. Attempting fallback.")
                         self._server_reachable = False
                except Exception as err:
                    _LOGGER.warning("Error initializing remote detector: %s", err)
                    self._server_reachable = False

            # 2. Fallback to Local if Remote failed or doesn't exist
            if not detector_ok and self._shape_detector:
                try:
                    # Switch to Local
                    await self._shape_detector.async_init()
                    self._spell_tracker._detector = self._shape_detector
                    detector_ok = True
                    _LOGGER.info("Using Local Shape Spell Detector as Remote is unavailable.")
                except Exception as err:
                    _LOGGER.warning("Failed to initialize shape detector: %s", err)

            if not detector_ok:
                 _LOGGER.warning("NO Spell Detector available! Spell tracking will simply fail.")

        except Exception as err:
            self._server_reachable = False
            _LOGGER.warning("Failed to initialize spell detector session: %s", err)

    async def async_spell_tracker_close(self) -> None:
        """Close spell tracker session but keep the object."""
        if self._spell_tracker is not None:
            _LOGGER.debug("Closing spell tracker session")
            await self._spell_tracker.close()
            # Do NOT set self._spell_tracker = None to keep upload state


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
