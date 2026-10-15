"""Home Assistant device wrapper for a Magic Caster Wand."""

import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from blesession import SessionDropped, ble_session
from homeassistant.core import HomeAssistant

from ..common_ble.common import BLEData, build_macro, build_set_led_macro
from ..common_ble.macros import LedGroup, Macro
from ..common_ble.session_diagnostics import BLESessionDiagnostics
from .mcw import McwClient
from .remote_tensor_spell_detector import RemoteTensorSpellDetector
from .spell_tracker import SpellTracker

_LOGGER = logging.getLogger(__name__)


class McwDevice:
    """Data handler for Magic Caster Wand BLE device."""

    device_label = "Wand"

    def __init__(
        self,
        address: str,
        tflite_url: str = "http://b5e3f765-tflite-server:8000",
        model_name: str = "model.tflite",
        spell_timeout: int = 0,
        hass: HomeAssistant | None = None,
    ) -> None:
        """Initialize the device."""
        self.address = address
        self.diagnostics = BLESessionDiagnostics(address, "wand")
        if hass is not None:
            self.diagnostics.bind_hass(hass)
        self.tflite_url = tflite_url
        self.model_name = model_name
        self.client: BleakClient | None = None
        self._ble_session_stack: AsyncExitStack | None = None
        self._disconnecting = False
        self._connecting = False
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
        self._imu_streaming: bool = False
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
            # A cancelled older timer can finish after its replacement is
            # scheduled. Only clear the reference when this task still owns it.
            if self._spell_reset_timeout_task is asyncio.current_task():
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

        # Handle spell tracking start/stop when using server-side detection.
        # Gated on streaming being armed too: without IMU samples a cast can only
        # ever fail recognition, so lighting the casting LED would promise nothing.
        if self.spell_tracking_active:
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
        if spell_name and self._coordinator_spell and self.spell_tracking_active:
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

        if self.spell_tracking_active:
            for sample in data:
                self._spell_tracker.update(
                    ax=sample["accel_y"],
                    ay=-sample["accel_x"],
                    az=sample["accel_z"],
                    gx=sample["gyro_y"],
                    gy=-sample["gyro_x"],
                    gz=sample["gyro_z"],
                )

    def _reset_cast_state(self) -> None:
        """Drop any in-flight cast so it cannot bleed across a reconnect.

        Disconnecting mid-cast leaves the recording open and button_all latched
        true. The wand reports buttons as released while disconnected, so without
        this the next press is not seen as a transition (no cast starts), and the
        samples from the interrupted cast would be prepended to the following one.
        """
        self._imu_streaming = False
        self._button_all_pressed = False
        if self._spell_tracker is not None:
            self._spell_tracker.abort()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle BLE device disconnection.

        Callbacks from a superseded connection are ignored. bleak dispatches this
        through the event loop, so a quick reconnect can install a new client before
        the old link's callback runs. Acting on that late callback would tear down
        the connection that replaced it -- dropping _mcw and _imu_streaming while the
        wand is connected and streaming, which reads as the wand being live but spell
        tracking silently doing nothing until the switch is toggled.
        """
        if client is not self.client:
            _LOGGER.debug("Ignoring disconnect callback from a superseded connection")
            return

        _LOGGER.debug("Disconnected from Magic Caster Wand")
        if not self._disconnecting and not self._connecting:
            self.diagnostics.record_failure(
                "connection", "session", SessionDropped("The wand disconnected unexpectedly")
            )
        self.client = None
        self._mcw = None
        self._reset_cast_state()
        # The wand reports buttons as released while disconnected; keep the
        # retained button sensors from showing a press that can no longer end.
        if self._coordinator_buttons:
            self._coordinator_buttons.async_set_updated_data(
                {key: False for key in ("button_1", "button_2", "button_3", "button_4", "button_all")}
            )
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

        if self._ble_session_stack is not None:
            await self._close_ble_session()

        trace = self.diagnostics.new_trace()
        client: BleakClient | None = None
        session_stack = AsyncExitStack()
        self._connecting = True
        try:
            await session_stack.__aenter__()
            self._ble_session_stack = session_stack
            client = await session_stack.enter_async_context(
                ble_session(
                    ble_device,
                    trace=trace,
                    name=ble_device.address,
                    disconnected_callback=self._on_disconnect,
                )
            )
            self.client = client

            if not client.is_connected:
                trace.fail("session")
                self.diagnostics.record("connect", trace, SessionDropped("Disconnected during connection setup"))
                await self._cleanup_failed_connection(client)
                return False

            # Update basic device info
            if not self._data.name:
                self._data.name = ble_device.name or "Magic Caster Wand"
            if not self._data.address:
                self._data.address = ble_device.address
            if not self._data.identifier:
                self._data.identifier = ble_device.address.replace(":", "")[-8:]
            self._mcw = McwClient(client)
            if hasattr(self._mcw, "register_error_callback"):
                self._mcw.register_error_callback(
                    lambda err: self.diagnostics.record_failure("notification", "notification", err)
                )
            self._mcw.register_callback(
                self._callback_spell,
                self._callback_battery,
                self._callback_buttons,
                self._callback_calibration,
                self._callback_imu,
            )
            with trace.timed("subscribe"):
                await self._mcw.start_notify()
            with trace.timed("initialize"):
                await self._refresh_model()
            await self._resume_imu_streaming()
            if self.client is not client or not client.is_connected:
                trace.fail("session")
                self.diagnostics.record("connect", trace, SessionDropped("Disconnected during connection setup"))
                await self._cleanup_failed_connection(client)
                return False

            _LOGGER.debug("Connected to Magic Caster Wand: %s, %s", ble_device.address, self.model)
            if self._coordinator_connection:
                self._coordinator_connection.async_set_updated_data(True)
            self.diagnostics.record("connect", trace)
            return True

        except asyncio.CancelledError:
            await self._cleanup_failed_connection(client)
            raise
        except Exception as err:
            self.diagnostics.record("connect", trace, err)
            await self._cleanup_failed_connection(client)
            _LOGGER.warning("Failed to connect to %s: %s", ble_device.address, err)
            return False
        finally:
            self._connecting = False

    async def _cleanup_failed_connection(self, client: BleakClient | None) -> None:
        """Release a link whose notification or device initialization failed."""
        self._disconnecting = True
        try:
            if client is not None and self._mcw is not None and self._mcw.client is client:
                try:
                    await self._mcw.stop_notify()
                except Exception as err:
                    _LOGGER.debug("Failed to stop notifications after connect failure: %s", err)
        finally:
            try:
                if self._ble_session_stack is not None:
                    await self._close_ble_session()
                elif client is not None and client.is_connected:
                    await client.disconnect()
            except Exception as err:
                _LOGGER.debug("Failed to disconnect after connect failure: %s", err)
            finally:
                if client is None or self.client is client:
                    self.client = None
                    self._mcw = None
                    self._reset_cast_state()
                    if self._coordinator_connection:
                        self._coordinator_connection.async_set_updated_data(False)
                self._disconnecting = False

    async def _close_ble_session(self) -> None:
        """Close the context that owns the active BLE connection."""
        stack = self._ble_session_stack
        self._ble_session_stack = None
        if stack is not None:
            await stack.aclose()

    async def _refresh_model(self) -> None:
        """Ask the wand for its model, if it is still unknown.

        Safe to call on an open connection: init_wand() only rewrites the button
        thresholds, and the client caches the device id after the first answer.
        """
        if self.model or not self._mcw:
            return
        await self._mcw.init_wand()
        self.model = await self._mcw.get_wand_device_id()

    async def _resume_imu_streaming(self) -> None:
        """Re-arm IMU streaming if spell tracking is meant to be running.

        IMU streaming is firmware state that dies with the connection, while the
        detector session that gates the button and IMU callbacks is owned by this
        object and outlives it. Without this, a reconnect leaves the two disagreeing:
        the callbacks still fire and light the casting LED, but no IMU samples ever
        arrive, so every cast is recognized from a single position and silently
        discarded until the Spell Tracking switch is toggled off and on again.

        A failure here must not be swallowed: reporting the wand as tracking while
        it is not is the very state this method exists to prevent, so _imu_streaming
        stays False and the Spell Tracking switch shows off, which is both truthful
        and the thing the user can act on.
        """
        if not self.spell_tracking_wanted or not self._mcw:
            return
        try:
            await self._mcw.imu_streaming_start()
            self._imu_streaming = True
            _LOGGER.debug("Resumed IMU streaming after connect")
        except Exception as err:
            self._imu_streaming = False
            self.diagnostics.record_failure("imu_streaming_start", "transfer", err)
            _LOGGER.warning(
                "Failed to resume IMU streaming after connect: %s. "
                "Spell tracking is off until the Spell Tracking switch is toggled",
                err,
            )

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
        self._disconnecting = True
        await self._cancel_background_tasks()
        # Before the client check: an explicit disconnect must clear the cast even
        # if the link is already gone, and _on_disconnect does not always fire.
        self._reset_cast_state()

        try:
            if self.client and self.client.is_connected and self._mcw:
                try:
                    await self._mcw.imu_streaming_stop()
                except Exception as imu_err:
                    _LOGGER.debug("Failed to stop IMU streaming during disconnect: %s", imu_err)
                await self._mcw.stop_notify()
        except Exception as err:
            _LOGGER.warning("Error during disconnect: %s", err)
        finally:
            try:
                if self._ble_session_stack is not None:
                    await self._close_ble_session()
                elif self.client and self.client.is_connected:
                    await self.client.disconnect()
            except Exception as err:
                _LOGGER.warning("Error closing BLE session: %s", err)
            finally:
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
                self._disconnecting = False

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Update device data. Sends keep-alive if connected."""
        # Learn the model as soon as possible, but never at the cost of the
        # connection. connect() returns True immediately for an open connection
        # without reaching its model fetch, so asking directly is the only way to
        # get it without dropping what the user opened with the Connect switch.
        if ble_device and not self.model:
            if self.is_connected():
                await self._refresh_model()
            elif await self.connect(ble_device):
                # Only connected to read the model, so let go again.
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
        await self.diagnostics.run_operation(
            "send_macro",
            lambda: self._mcw.send_macro(macro),
            connected=self.is_connected() and self._mcw is not None,
        )

    async def send_macro_parse(self, commands: list) -> None:
        """Convert service commands into a Macro and send it."""
        await self.send_macro(build_macro(commands))

    async def set_led(self, group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> None:
        """Set LED color."""
        await self.send_macro(build_set_led_macro(group, r, g, b, duration))

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
        """Get the current spell detection mode.

        Follows intent rather than streaming state: which detector is configured
        does not change just because a reconnect has yet to re-arm the stream.
        """
        return "Server" if self.spell_tracking_wanted else "Wand"

    @property
    def spell_tracking_wanted(self) -> bool:
        """Whether spell tracking is meant to be running.

        The detector session is owned by this object and survives a disconnect,
        so this is the user's intent: it stays true across a reconnect and is what
        decides whether streaming should be re-armed.
        """
        return self._spell_tracker is not None and self._spell_tracker.is_active

    @property
    def spell_tracking_active(self) -> bool:
        """Whether spell tracking is actually running.

        Intent alone is not enough -- IMU streaming is firmware state that a
        reconnect clears and a failed resume never restores. Requiring both means
        this cannot claim tracking while no samples are arriving.
        """
        return self.spell_tracking_wanted and self._imu_streaming

    @property
    def server_reachable(self) -> bool:
        """Check if the TFLite server is reachable."""
        return self._server_reachable

    async def buzz(self, duration: int) -> None:
        """Vibrate the wand."""
        await self.diagnostics.run_operation(
            "buzz", lambda: self._mcw.buzz(duration), connected=self.is_connected() and self._mcw is not None
        )

    async def clear_leds(self) -> None:
        """Clear all LEDs."""
        await self.diagnostics.run_operation(
            "clear_leds", lambda: self._mcw.led_off(), connected=self.is_connected() and self._mcw is not None
        )

    async def send_button_calibration(self) -> None:
        """Send button calibration packet."""
        await self.diagnostics.run_operation(
            "button_calibration",
            lambda: self._mcw.calibration_button(),
            connected=self.is_connected() and self._mcw is not None,
        )

    async def send_imu_calibration(self) -> None:
        """Send IMU calibration packet."""
        await self.diagnostics.run_operation(
            "imu_calibration",
            lambda: self._mcw.calibration_imu(),
            connected=self.is_connected() and self._mcw is not None,
        )

    async def imu_streaming_start(self) -> None:
        """Start IMU streaming."""
        if self.is_connected() and self._mcw:
            await self.diagnostics.run_operation(
                "imu_streaming_start",
                lambda: self._mcw.imu_streaming_start(),
                connected=True,
            )
            self._imu_streaming = True

    async def imu_streaming_stop(self) -> None:
        """Stop IMU streaming."""
        self._reset_cast_state()
        if self.is_connected() and self._mcw:
            await self.diagnostics.run_operation(
                "imu_streaming_stop", lambda: self._mcw.imu_streaming_stop(), connected=True
            )

    async def async_spell_tracker_init(self) -> bool:
        """Initialize spell tracking and report whether the model is ready."""
        if self._spell_tracker is None:
            self._init_spell_tracker()

        if self._spell_tracker is None:
            _LOGGER.warning("Spell tracker not created, cannot initialize")
            return False

        try:
            # Perform connectivity check before opening full session
            self._server_reachable = await self._spell_tracker.detector.check_connectivity()
            if self._server_reachable:
                # async_init will handle session creation and one-time upload
                await self._spell_tracker.detector.async_init()
                _LOGGER.debug("Spell tracker session initialized and verified")
                return True
            else:
                _LOGGER.warning(
                    "TFLite server at %s is not reachable. Spell detection will not be available.",
                    self._spell_tracker.detector._base_url,
                )
        except asyncio.CancelledError:
            self._server_reachable = False
            try:
                await self._spell_tracker.close()
            except Exception as close_err:
                _LOGGER.debug("Failed to close detector after initialization cancellation: %s", close_err)
            raise
        except Exception as err:
            self._server_reachable = False
            _LOGGER.warning("Failed to initialize remote spell detector session: %s", err)
            try:
                await self._spell_tracker.close()
            except Exception as close_err:
                _LOGGER.debug("Failed to close detector after initialization error: %s", close_err)

        return False

    async def async_spell_tracker_close(self) -> None:
        """Stop spell tracking and close its detector session, keeping the tracker."""
        self._reset_cast_state()
        self._server_reachable = False
        if self._spell_tracker is not None:
            _LOGGER.debug("Closing spell tracker session")
            try:
                await self._spell_tracker.close()
            except Exception as err:
                _LOGGER.warning("Failed to close spell tracker session: %s", err)
        # Keep the tracker object so it can be initialized again if tracking is re-enabled.
