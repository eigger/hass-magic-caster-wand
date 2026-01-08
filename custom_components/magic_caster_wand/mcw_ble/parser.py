"""Parser for Mcw BLE devices"""

import dataclasses
import logging
import asyncio

# from logging import Logger
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from .mcw import McwClient
import typing

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BLEData:
    """Response data with information about the Mcw device"""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    model: str = ""
    serial_number: str = ""
    density: int | None = None
    printspeed: int | None = None
    labeltype: int | None = None
    languagetype: int | None = None
    autoshutdowntime: int | None = None
    devicetype: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )


# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class McwDevice:
    """Data for Mcw BLE sensors."""

    def __init__(self, address):
        self.address = address
        self.client: BleakClient = None
        self.model = None
        self._callback = None
        self._data = BLEData()
        self._mcw = None
        self._coordinator_spell = None
        self._coordinator_battery = None
        self._coordinator_button = None
        super().__init__()

    def register_coordinator(self, cn_spell, cn_battery, cn_button):
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery
        self._coordinator_button = cn_button

    def callback_spell(self, data):
        self._coordinator_spell.async_set_updated_data(data)

    def callback_battery(self, data):
        self._coordinator_battery.async_set_updated_data(data)

    def callback_button(self, data):
        self._coordinator_button.async_set_updated_data(data)

    def is_connected(self):
        if self.client:
            try:
                if self.client.is_connected:
                    return True
            except Exception as e:
                pass
        return False

    async def connect(self, ble_device: BLEDevice):
        if self.client and self.client.is_connected:
            return True
        self.client = await establish_connection(
            BleakClient, ble_device, ble_device.address
        )
        if not self.client.is_connected:
            return False

        self._mcw = McwClient(self.client)
        self._mcw.register_callbacks(self.callback_spell, self.callback_battery, self.callback_button)
        await self._mcw.start_notify()
        await self._mcw.init_wand()
        device_id = await self._mcw.get_wand_device_id()
        wand_type = await self._mcw.get_wand_type()
        self.model = f"{device_id} ({wand_type})" if wand_type != "UNKNOWN" else device_id
        return True
    
    async def disconnect(self):
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            except Exception as e:
                _LOGGER.warning(f"Already disconnected: {e}")

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Connects to the device through BLE and retrieves relevant data"""
        if not self._data.name:
            self._data.name = ble_device.name or "(no such device)"
        if not self._data.address:
            self._data.address = ble_device.address

        if not self._mcw:
            if await self.connect(ble_device):
                await self.disconnect()

        if self.is_connected():
            await self._mcw.keep_alive()

        _LOGGER.debug("Obtained BLEData: %s", self._data)
        return self._data


class McwBluetoothDeviceData(BluetoothData):
    """Data for BTHome Bluetooth devices."""

    def __init__(self) -> None:
        super().__init__()

        # The last service_info we saw that had a payload
        # We keep this to help in reauth flows where we want to reprocess and old
        # value with a new bindkey.
        self.last_service_info: BluetoothServiceInfoBleak | None = None

        self.pending = True


    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        # if not super().supported(data):
        #     return False
        return True
