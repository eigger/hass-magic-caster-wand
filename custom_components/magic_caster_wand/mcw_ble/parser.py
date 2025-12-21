"""Parser for Mcw BLE devices"""

import dataclasses
import logging
import asyncio

# from logging import Logger
from PIL import Image, ImageOps
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
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
        self.lock = asyncio.Lock()
        self.set_sound = None
        self.model = None
        self._callback = None
        self._data = BLEData()
        self._mcw = None
        self._coordinator = None
        super().__init__()

    def register_coordinator(self, cn):
        self._coordinator = cn

    def callback(self, data):
        self._coordinator.async_set_updated_data(data)

    async def update_device(self, ble_device: BLEDevice) -> BLEData:
        """Connects to the device through BLE and retrieves relevant data"""
        async with self.lock:
            if not self._mcw:
                client = await establish_connection(
                    BleakClient, ble_device, ble_device.address
                )
                if not client.is_connected:
                    raise RuntimeError("could not connect to thermal printer")
                
                self._data.name = ble_device.name or "(no such device)"
                self._data.address = ble_device.address
                self._mcw = McwClient(client)
                self._mcw.register_callbck(self.callback)
                await self._mcw.start_notify()

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
