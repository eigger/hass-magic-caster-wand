"""Parser for Magic Caster Wand BLE devices."""

import asyncio
import dataclasses
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from .mcb import CHARGENOTIFY, LIDNOTIFY, WANDNOTIFY, McbClient
from .mcw import LedGroup, Macro, McwClient
from .remote_tensor_spell_detector import RemoteTensorSpellDetector
from .spell_tracker import SpellTracker

_LOGGER = logging.getLogger(__name__)


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
    sensors: dict[str, str | float | None] = dataclasses.field(default_factory=lambda: {})


# A duration of 0 means "hold indefinitely"; the wire format has no such value,
# so it is sent as the maximum the 16-bit duration field can hold.
HOLD_DURATION_MS = 65535


def resolve_led_group(group_val: object) -> LedGroup:
    """Resolve an LED group given either its index or its name."""
    if isinstance(group_val, LedGroup):
        return group_val
    if isinstance(group_val, int):
        return LedGroup(group_val)
    return LedGroup[str(group_val).upper()]


def _clamp_duration(duration: int, what: str) -> int:
    """Fit a duration into the 16-bit field the wire format uses.

    Durations are packed as '<H'. Without this, an out-of-range value raises
    struct.error at send time -- after the macro has been built -- which would
    discard the whole sequence rather than just the offending value.
    """
    clamped = max(0, min(HOLD_DURATION_MS, duration))
    if clamped != duration:
        _LOGGER.warning("%s duration %d ms out of range, using %d ms", what, duration, clamped)
    return clamped


def build_macro(commands: list) -> Macro:
    """Build a Macro from the command list accepted by the send_macro service.

    Each command is either a mapping with a single command key (``{"delay": 100}``)
    or, for commands that take no argument, the bare command name (``"clear"``).
    Unknown commands are logged and skipped so one bad entry does not discard
    the whole sequence.
    """
    macro = Macro()

    for cmd in commands:
        if isinstance(cmd, str):
            key, value = cmd, None
        elif isinstance(cmd, dict) and len(cmd) == 1:
            key, value = next(iter(cmd.items()))
        else:
            _LOGGER.warning("Skipping malformed macro command: %r", cmd)
            continue

        try:
            if key == "changeled":
                params = value or {}
                group = resolve_led_group(params.get("group", "TIP"))
                r, g, b = params.get("rgb", (255, 255, 255))
                duration = int(params.get("duration", 800)) or HOLD_DURATION_MS
                macro.add_led(group, int(r), int(g), int(b), _clamp_duration(duration, "changeled"))
            elif key == "clear":
                macro.add_clear()
            elif key == "delay":
                macro.add_delay(_clamp_duration(int(value), "delay"))
            elif key == "buzz":
                macro.add_buzz(_clamp_duration(int(value), "buzz"))
            elif key == "loop":
                macro.add_loop()
            elif key == "set_loops":
                macro.add_set_loops(int(value))
            elif key == "wait":
                macro.add_wait()
            else:
                _LOGGER.warning("Skipping unknown macro command: %r", key)
        except (KeyError, ValueError, TypeError) as err:
            _LOGGER.warning("Skipping invalid macro command %r: %s", cmd, err)

    return macro


def build_set_led_macro(group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> Macro:
    """Build the macro behind the set_led service.

    A non-zero duration fades the LED in and then clears it, so the colour lasts
    exactly that long. A duration of 0 holds the colour until it is cleared.
    """
    hold = duration == 0
    fade = HOLD_DURATION_MS if hold else _clamp_duration(duration, "set_led")
    macro = Macro().add_led(group, r, g, b, fade)
    if not hold:
        macro.add_wait().add_clear()
    return macro


class McwDevice:
    """Data handler for Magic Caster Wand BLE device."""

    def __init__(
        self,
        address: str,
        tflite_url: str = "http://b5e3f765-tflite-server:8000",
        model_name: str = "model.tflite",
        spell_timeout: int = 0,
    ) -> None:
        """Initialize the device."""
        self.address = address
        self.tflite_url = tflite_url
        self.model_name = model_name
        self.client: BleakClient | None = None
        self.model: str | None = None
        self._mcw: McwClient | None = None
        self._data = BLEData()
        self._coordinator_spell = None
        self._coordinator_battery = None
        self._coordinator_buttons = None
        self._coordinator_calibration = None
        self._coordinator_imu = None
        self._coordinator_connection = None
        self._spell_timeout = spell_timeout
        self._spell_tracker: SpellTracker | None = None
        self._button_all_pressed: bool = False
        self._spell_reset_timeout_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._casting_led_color: tuple[int, int, int] = (0, 0, 255)  # Default color: blue
        self._server_reachable: bool = False

        self._init_spell_tracker()

    def _init_spell_tracker(self) -> None:
        """Initialize the spell tracker."""
        try:
            # Persistent detector and tracker
            self._spell_tracker = SpellTracker(
                RemoteTensorSpellDetector(
                    model_name=self.model_name,
                    base_url=self.tflite_url,
                )
            )
            _LOGGER.debug("Persistent spell tracker created")
        except Exception as err:
            _LOGGER.warning("Failed to create spell detector: %s", err)

    def register_coordinator(
        self, cn_spell, cn_battery, cn_buttons, cn_calibration=None, cn_imu=None, cn_connection=None
    ) -> None:
        """Register coordinators for spell, battery, button, calibration, and connection updates."""
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery
        self._coordinator_buttons = cn_buttons
        self._coordinator_calibration = cn_calibration
        self._coordinator_imu = cn_imu
        self._coordinator_connection = cn_connection

    def _spawn(self, coro) -> None:
        """Run a coroutine in the background, keeping a reference to the task.

        The event loop only holds a weak reference to a task, so one that is
        not stored can be garbage collected mid-flight. Holding it until it
        finishes also means an exception is retrieved rather than surfacing
        later as "Task exception was never retrieved".
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _schedule_spell_reset(self) -> None:
        """Schedule a reset of the spell sensor back to 'awaiting' after the configured timeout."""
        # Cancel any existing timeout task
        if self._spell_reset_timeout_task is not None:
            self._spell_reset_timeout_task.cancel()
            self._spell_reset_timeout_task = None

        # Only schedule if timeout is greater than 0
        if self._spell_timeout > 0:
            self._spell_reset_timeout_task = asyncio.create_task(self._async_reset_spell_after_timeout())

    async def _async_reset_spell_after_timeout(self) -> None:
        """Reset the spell sensor to 'awaiting' after the configured timeout."""
        try:
            await asyncio.sleep(self._spell_timeout)
            if self._coordinator_spell:
                _LOGGER.debug("Spell timeout reached, resetting to 'awaiting'")
                self._coordinator_spell.async_set_updated_data("awaiting")
        except asyncio.CancelledError:
            # Task was cancelled (likely because a new spell was detected)
            pass
        finally:
            self._spell_reset_timeout_task = None

    def _callback_spell(self, data: str) -> None:
        """Handle spell detection callback from wand-native detection."""
        if self._coordinator_spell:
            self._coordinator_spell.async_set_updated_data(data)
            self._schedule_spell_reset()

    def _callback_battery(self, data: float) -> None:
        """Handle battery update callback."""
        if self._coordinator_battery:
            self._coordinator_battery.async_set_updated_data(data)

    def _callback_buttons(self, data: dict[str, bool]) -> None:
        """Handle button state update callback."""
        if self._coordinator_buttons:
            self._coordinator_buttons.async_set_updated_data(data)

        # Handle spell tracking start/stop when using server-side detection
        if (
            self._spell_tracker is not None
            and self._spell_tracker.detector is not None
            and self._spell_tracker.detector.is_active
        ):
            button_all = data.get("button_all", False)

            # Transition: not pressed -> pressed = start tracking
            if button_all and not self._button_all_pressed:
                _LOGGER.debug("All buttons pressed, starting spell tracking")
                self._spawn(self._turn_on_casting_led())
                self._spell_tracker.start()

            # Transition: pressed -> not pressed = stop tracking and detect spell
            elif not button_all and self._button_all_pressed:
                _LOGGER.debug("Buttons released, stopping spell tracking")
                self._spawn(self._turn_off_casting_led())
                self._spawn(self._async_stop_and_detect_spell())

            self._button_all_pressed = button_all

    async def _async_stop_and_detect_spell(self) -> None:
        """Stop spell tracking and detect spell asynchronously."""
        if self._spell_tracker is None:
            return

        spell_name = await self._spell_tracker.stop()
        if spell_name and self._coordinator_spell:
            _LOGGER.debug("Server-side spell detected: %s", spell_name)
            self._coordinator_spell.async_set_updated_data(spell_name)
            self._schedule_spell_reset()
            await self.buzz(100)

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

        if (
            self._spell_tracker is not None
            and self._spell_tracker.detector is not None
            and self._spell_tracker.detector.is_active
        ):
            for sample in data:
                self._spell_tracker.update(
                    ax=sample["accel_y"],
                    ay=-sample["accel_x"],
                    az=sample["accel_z"],
                    gx=sample["gyro_y"],
                    gy=-sample["gyro_x"],
                    gz=sample["gyro_z"],
                )

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle BLE device disconnection."""
        _LOGGER.debug("Disconnected from Magic Caster Wand")
        self.client = None
        self._mcw = None
        if self._coordinator_connection:
            self._coordinator_connection.async_set_updated_data(False)

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
                BleakClient, ble_device, ble_device.address, disconnected_callback=self._on_disconnect
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
                await self._mcw.init_wand()
                self.model = await self._mcw.get_wand_device_id()

            _LOGGER.debug("Connected to Magic Caster Wand: %s, %s", ble_device.address, self.model)
            if self._coordinator_connection:
                self._coordinator_connection.async_set_updated_data(True)
            return True

        except Exception as err:
            _LOGGER.warning("Failed to connect to %s: %s", ble_device.address, err)
            return False

    async def _cancel_background_tasks(self) -> None:
        """Cancel anything still running so it cannot outlive the config entry."""
        if self._spell_reset_timeout_task is not None:
            self._spell_reset_timeout_task.cancel()
            self._spell_reset_timeout_task = None

        pending = list(self._background_tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._background_tasks.clear()

    async def disconnect(self) -> None:
        """Disconnect from the BLE device."""
        await self._cancel_background_tasks()

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
            except Exception as err:
                _LOGGER.warning("Error during disconnect: %s", err)
            finally:
                # Reset all states on disconnect
                if self._coordinator_buttons:
                    self._coordinator_buttons.async_set_updated_data(
                        {
                            "button_1": False,
                            "button_2": False,
                            "button_3": False,
                            "button_4": False,
                            "button_all": False,
                        }
                    )
                if self._coordinator_connection:
                    self._coordinator_connection.async_set_updated_data(False)

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Update device data. Sends keep-alive if connected."""
        # Probe for the model only while it is still unknown, and only when the
        # user has not already opened a connection: connect() returns True for an
        # existing connection, so without this guard the disconnect below would
        # drop the user's connection on every poll.
        if ble_device and not self.model and not self.is_connected():
            if await self.connect(ble_device):
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

    async def send_macro_parse(self, commands: list) -> None:
        """Convert service commands into a Macro and send it."""
        if self.is_connected() and self._mcw:
            await self._mcw.send_macro(build_macro(commands))

    async def set_led(self, group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> None:
        """Set LED color."""
        if self.is_connected() and self._mcw:
            await self._mcw.send_macro(build_set_led_macro(group, r, g, b, duration))

    @property
    def casting_led_color(self) -> tuple[int, int, int]:
        """Get the current casting LED color."""
        return self._casting_led_color

    @casting_led_color.setter
    def casting_led_color(self, value: tuple[int, int, int]) -> None:
        """Set the casting LED color."""
        self._casting_led_color = value

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
            await self._mcw.led_off()

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
        """Initialize spell tracker and detector session."""
        if self._spell_tracker is None:
            self._init_spell_tracker()

        if self._spell_tracker is None:
            _LOGGER.warning("Spell tracker not created, cannot initialize")
            return

        try:
            # Perform connectivity check before opening full session
            self._server_reachable = await self._spell_tracker.detector.check_connectivity()
            if self._server_reachable:
                # async_init will handle session creation and one-time upload
                await self._spell_tracker.detector.async_init()
                _LOGGER.debug("Spell tracker session initialized and verified")
            else:
                _LOGGER.warning(
                    "TFLite server at %s is not reachable. Spell detection will not be available.",
                    self._spell_tracker.detector._base_url,
                )
        except Exception as err:
            self._server_reachable = False
            _LOGGER.warning("Failed to initialize remote spell detector session: %s", err)

    async def async_spell_tracker_close(self) -> None:
        """Close spell tracker session but keep the object."""
        if self._spell_tracker is not None:
            _LOGGER.debug("Closing spell tracker session")
            await self._spell_tracker.close()
            # Do NOT set self._spell_tracker = None to keep upload state


class McbDevice:
    """Data handler for Magic Caster Box BLE device."""

    def __init__(self, address: str) -> None:
        """Initialize the device."""
        self.address = address
        self.client: BleakClient | None = None
        self.model: str | None = None
        self._mcb: McbClient | None = None
        self._data = BLEData()
        self._coordinator_battery = None
        self._coordinator_lid = None
        self._coordinator_charge = None
        self._coordinator_wand = None
        self._coordinator_connection = None

    def register_coordinator(
        self,
        cn_battery,
        cn_lid,
        cn_charge,
        cn_wand,
        cn_connection=None,
    ) -> None:
        """Register coordinators for all MCB notifications.

        ``cn_charge`` backs the USB-plugged entity: the box reports the USB
        power state through its charge notification.
        """
        self._coordinator_battery = cn_battery
        self._coordinator_lid = cn_lid
        self._coordinator_charge = cn_charge
        self._coordinator_wand = cn_wand
        self._coordinator_connection = cn_connection

    def _callback_battery(self, data: float) -> None:
        """Handle battery update callback."""
        if self._coordinator_battery:
            self._coordinator_battery.async_set_updated_data(data)

    def _callback_lid(self, data: LIDNOTIFY) -> None:
        """Handle lid notify callback."""
        if self._coordinator_lid:
            self._coordinator_lid.async_set_updated_data(data)

    def _callback_wand(self, data: WANDNOTIFY) -> None:
        """Handle wand-present callback."""
        if self._coordinator_wand:
            self._coordinator_wand.async_set_updated_data(data)

    def _callback_charge(self, data: CHARGENOTIFY) -> None:
        """Handle charging state callback."""
        if self._coordinator_charge:
            self._coordinator_charge.async_set_updated_data(data)

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle BLE device disconnection."""
        _LOGGER.debug("Disconnected from Magic Caster Box")
        self.client = None
        self._mcb = None
        if self._coordinator_connection:
            self._coordinator_connection.async_set_updated_data(False)

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
                BleakClient, ble_device, ble_device.address, disconnected_callback=self._on_disconnect
            )

            if not self.client.is_connected:
                return False

            # Update basic device info
            if not self._data.name:
                self._data.name = ble_device.name or "Magic Caster Box"
            if not self._data.address:
                self._data.address = ble_device.address
            if not self._data.identifier:
                self._data.identifier = ble_device.address.replace(":", "")[-8:]
            self._mcb = McbClient(self.client)
            self._mcb.register_callback(
                self._callback_battery,
                self._callback_lid,
                self._callback_wand,
                self._callback_charge,
            )
            await self._mcb.start_notify()
            if not self.model:
                self.model = await self._mcb.get_box_device_id()

            _LOGGER.debug("Connected to Magic Caster Box: %s, %s", ble_device.address, self.model)
            if self._coordinator_connection:
                self._coordinator_connection.async_set_updated_data(True)
            return True

        except Exception as err:
            _LOGGER.warning("Failed to connect to %s: %s", ble_device.address, err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the BLE device."""
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            except Exception as err:
                _LOGGER.warning("Error during disconnect: %s", err)
            finally:
                if self._coordinator_connection:
                    self._coordinator_connection.async_set_updated_data(False)

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Update device data. Sends keep-alive if connected."""
        # Probe for the model only while it is still unknown, and only when the
        # user has not already opened a connection: connect() returns True for an
        # existing connection, so without this guard the disconnect below would
        # drop the user's connection on every poll.
        if ble_device and not self.model and not self.is_connected():
            if await self.connect(ble_device):
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
        if self.is_connected() and self._mcb:
            await self._mcb.send_macro(macro)

    async def send_macro_parse(self, commands: list) -> None:
        """Convert service commands into a Macro and send it."""
        if self.is_connected() and self._mcb:
            await self._mcb.send_macro(build_macro(commands))

    async def set_led(self, group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> None:
        """Set LED color."""
        if self.is_connected() and self._mcb:
            await self._mcb.send_macro(build_set_led_macro(group, r, g, b, duration))

    async def clear_leds(self) -> None:
        """Clear all LEDs."""
        if self.is_connected() and self._mcb:
            await self._mcb.led_off()

    async def buzz(self, duration: int) -> None:
        """Ignore vibration requests: the box has no vibration motor.

        The vibrate service targets the whole integration, so a box can be
        picked in the UI. Without this the call would raise AttributeError.
        """
        _LOGGER.debug("Ignoring vibrate request: the Magic Caster Box has no vibration motor")


class McwBluetoothDeviceData(BluetoothData):
    """Bluetooth device data for Magic Caster Wand."""

    # Magic Caster Wand Service UUID (from mcw.py)
    SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
    # Device name prefix
    DEVICE_NAME_PREFIX = "MCW-"
    device_type = "mcw"

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


class McbBluetoothDeviceData(BluetoothData):
    """Bluetooth device data for Magic Caster Box."""

    # Magic Caster Box Service UUID (from mcb.py)
    SERVICE_UUID = "57420001-587e-48a0-974c-54686f72c577"
    # Device name prefix
    DEVICE_NAME_PREFIX = "MCB-"
    device_type = "mcb"

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        self.pending = True

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is a supported Magic Caster Box."""
        # Check device name starts with "MCB-"
        if not data.name or not data.name.startswith(self.DEVICE_NAME_PREFIX):
            return False

        # Check for Magic Caster Box Service UUID
        # service_uuids_lower = [uuid.lower() for uuid in data.service_uuids]
        # if self.SERVICE_UUID.lower() not in service_uuids_lower:
        #     return False

        return True
