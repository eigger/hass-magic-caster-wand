"""Parser for Magic Caster Wand BLE devices."""

import dataclasses
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from .mcw import McwClient, LedGroup, Macro

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

    def register_coordinator(self, cn_spell, cn_battery, cn_buttons, cn_calibration=None) -> None:
        """Register coordinators for spell, battery, button, and calibration updates."""
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery
        self._coordinator_buttons = cn_buttons
        self._coordinator_calibration = cn_calibration

    def _callback_spell(self, data: str) -> None:
        """Handle spell detection callback."""
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

    def _callback_calibration(self, data: dict[str, bool]) -> None:
        """Handle calibration state update callback."""
        if self._coordinator_calibration:
            self._coordinator_calibration.async_set_updated_data(data)

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
            self._mcw.register_callback(self._callback_spell, self._callback_battery, self._callback_buttons, self._callback_calibration)
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
                        await self._mcw.stop_notify()
                    await self.client.disconnect()
                    _LOGGER.debug("Disconnected from Magic Caster Wand")
            except Exception as err:
                _LOGGER.warning("Error during disconnect: %s", err)
            finally:
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
