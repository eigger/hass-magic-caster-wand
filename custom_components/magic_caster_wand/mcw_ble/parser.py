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
        self.lock = asyncio.Lock()
        self.model = None
        self._callback = None
        self._data = BLEData()
        self._mcw = None
        self._coordinator_spell = None
        self._coordinator_battery = None
        super().__init__()

    def register_coordinator(self, cn_spell, cn_battery):
        self._coordinator_spell = cn_spell
        self._coordinator_battery = cn_battery

    def callback_spell(self, data):
        self._coordinator_spell.async_set_updated_data(data)

    def callback_battery(self, data):
        self._coordinator_battery.async_set_updated_data(data)

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
        self._mcw.register_callbck(self.callback_spell, self.callback_battery)
        await self._mcw.start_notify()
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
        async with self.lock:
            if not self._data.name:
                self._data.name = ble_device.name or "(no such device)"
            if not self._data.address:
                self._data.address = ble_device.address

            try:
                # if not self._data.serial_number:
                #     self._data.serial_number = str(
                #         await self._mcw.request_request_box_address()
                #     )
                # if not self._data.hw_version:
                #     self._data.hw_version = str(
                #         await self._mcw.request_firmware().version
                #     )
                # if not self._data.sw_version:
                #     self._data.sw_version = str(
                #         await printer.get_info(InfoEnum.SOFTVERSION)
                #     )

                if self.is_connected():
                    heartbeat = await self._mcw.keep_alive()
                    #self._data.sensors["battery"] = float(heartbeat["powerlevel"]) * 25.0
            finally:
                pass




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
