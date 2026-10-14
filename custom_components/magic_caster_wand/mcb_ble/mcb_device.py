"""Home Assistant device wrapper for a Magic Caster Box."""

import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from blesession import ble_session

from ..common_ble.common import BLEData, build_macro, build_set_led_macro
from ..common_ble.macros import LedGroup, Macro
from .mcb import CHARGENOTIFY, LIDNOTIFY, WANDNOTIFY, McbClient

_LOGGER = logging.getLogger(__name__)


class McbDevice:
    """Data handler for Magic Caster Box BLE device."""

    device_label = "Box"

    def __init__(self, address: str) -> None:
        """Initialize the device."""
        self.address = address
        self.client: BleakClient | None = None
        self._ble_session_stack: AsyncExitStack | None = None
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
        """Handle BLE device disconnection.

        Ignores callbacks from a superseded connection, for the same reason as the
        wand: a late callback would otherwise clear _mcb and mark the box offline
        while it is in fact connected.
        """
        if client is not self.client:
            _LOGGER.debug("Ignoring disconnect callback from a superseded connection")
            return

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

        if self._ble_session_stack is not None:
            await self._close_ble_session()

        client: BleakClient | None = None
        session_stack = AsyncExitStack()
        try:
            await session_stack.__aenter__()
            self._ble_session_stack = session_stack
            client = await session_stack.enter_async_context(
                ble_session(
                    ble_device,
                    name=ble_device.address,
                    disconnected_callback=self._on_disconnect,
                )
            )
            self.client = client

            if not client.is_connected:
                await self._cleanup_failed_connection(client)
                return False

            # Update basic device info
            if not self._data.name:
                self._data.name = ble_device.name or "Magic Caster Box"
            if not self._data.address:
                self._data.address = ble_device.address
            if not self._data.identifier:
                self._data.identifier = ble_device.address.replace(":", "")[-8:]
            self._mcb = McbClient(client)
            self._mcb.register_callback(
                self._callback_battery,
                self._callback_lid,
                self._callback_wand,
                self._callback_charge,
            )
            await self._mcb.start_notify()
            await self._refresh_model()

            _LOGGER.debug("Connected to Magic Caster Box: %s, %s", ble_device.address, self.model)
            if self._coordinator_connection:
                self._coordinator_connection.async_set_updated_data(True)
            return True

        except asyncio.CancelledError:
            await self._cleanup_failed_connection(client)
            raise
        except Exception as err:
            await self._cleanup_failed_connection(client)
            _LOGGER.warning("Failed to connect to %s: %s", ble_device.address, err)
            return False

    async def _cleanup_failed_connection(self, client: BleakClient | None) -> None:
        """Release a link whose notification or device initialization failed."""
        try:
            if client is not None and self._mcb is not None and self._mcb.client is client:
                try:
                    await self._mcb.stop_notify()
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
                    self._mcb = None
                    if self._coordinator_connection:
                        self._coordinator_connection.async_set_updated_data(False)

    async def _close_ble_session(self) -> None:
        """Close the context that owns the active BLE connection."""
        stack = self._ble_session_stack
        self._ble_session_stack = None
        if stack is not None:
            await stack.aclose()

    async def _refresh_model(self) -> None:
        """Ask the box for its model, if it is still unknown.

        Safe to call on an open connection: the client caches the device id
        after the first answer.
        """
        if self.model or not self._mcb:
            return
        self.model = await self._mcb.get_box_device_id()

    async def disconnect(self) -> None:
        """Disconnect from the BLE device."""
        try:
            if self.client and self.client.is_connected and self._mcb:
                await self._mcb.stop_notify()
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
                if self._coordinator_connection:
                    self._coordinator_connection.async_set_updated_data(False)

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
