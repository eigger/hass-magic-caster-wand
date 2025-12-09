# mcw_ble.py

from __future__ import annotations
from enum import Enum
import logging
import struct
import traceback
from typing import Any, Callable, TypeVar
from asyncio import Event, wait_for, sleep
from PIL import Image
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from .const import SERVICE_WP6003, CHAR_CMD, CHAR_NOTI

_LOGGER = logging.getLogger(__name__)

# 예외 정의
class BleakCharacteristicMissing(BleakError):
    """Characteristic Missing"""

class BleakServiceMissing(BleakError):
    """Service Missing"""

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

def disconnect_on_missing_services(func: WrapFuncType) -> WrapFuncType:
    """Missing services"""
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except (BleakServiceMissing, BleakCharacteristicMissing):
            if self.client.is_connected:
                await self.client.clear_cache()
                await self.client.disconnect()
            raise
    return wrapper  # type: ignore

async def get_sensor_data(
    ble_device: BLEDevice,
) -> bytes:
    client: BleakClient | None = None
    try:
        _LOGGER.debug("connection: %s", ble_device)
        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        services = client.services
        for svc in services:
            for c in svc.characteristics:
                _LOGGER.debug(f"uuid: {svc.uuid}, char: {c}")

        mcw = McwClient(client)
        return await mcw.request_data()
    except Exception as e:
        _LOGGER.error(f"Fail get data: {e}")
        _LOGGER.error(traceback.print_exc())
    finally:
        if client and client.is_connected:
            await client.disconnect()
    return None

class McwClient:
       
    def __init__(
        self,
        client: BleakClient
    ) -> None:
        self.client = client
        self.event: Event = Event()
        self.command_data: bytes | None = None

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        await self.client.start_notify(CHAR_NOTI, self._notification_handler)
        await sleep(0.5)

    @disconnect_on_missing_services
    async def stop_notify(self) -> None:
        await self.client.stop_notify(CHAR_NOTI)

    @disconnect_on_missing_services
    async def write(self, uuid: str, data: bytes) -> None:
        _LOGGER.debug("Write UUID=%s data=%s", uuid, len(data))
        chunk = len(data)
        for i in range(0, len(data), chunk):
            await self.client.write_gatt_char(uuid, data[i : i + chunk])
            await sleep(0.05)

    def _notification_handler(self, _: Any, data: bytearray) -> None:
        if self.command_data == None:
            self.command_data = bytes(data)
            self.event.set()

    async def read(self, timeout: float = 5.0) -> bytes:
        await wait_for(self.event.wait(), timeout)
        data = self.command_data or b""
        _LOGGER.debug("Received: %s", data.hex())
        return data

    async def write_with_response(self, uuid, packet: bytes) -> bytes:
        self.command_data = None
        self.event.clear()
        await self.write(uuid, packet)
        return await self.read()
    
    #0xAB get data
    #0xAD calibration
    async def request_data(self) -> bytes:
        await self.start_notify()
        data = await self.write_with_response(CHAR_CMD, bytes([0xAB]))
        await self.stop_notify()
        return data
    