# mcw_ble.py

from __future__ import annotations
from enum import Enum
import logging
import struct
import traceback
from typing import Any, Callable, TypeVar
from asyncio import Event, wait_for, sleep
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .protocol import Protocol, ResponseFirmware, ResponseBoxAddress, ResponseWandType, EventSpell, EventButton, WandModel, ResponseSerialNumber, ResponseSKU, \
    ResponseManufacturerID, ResponseDeviceID, ResponseEdition, ResponseCompanionAddress

SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
COMMAND_UUID = "57420002-587e-48a0-974c-544d6163c577"
STREAM_UUID = "57420003-587e-48a0-974c-544d6163c577"

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
            try:
                if self.client.is_connected:
                    await self.client.clear_cache()
                    await self.client.disconnect()
            except Exception:
                pass
            raise
    return wrapper  # type: ignore

class McwClient:
       
    def __init__(
        self,
        client: BleakClient,
    ) -> None:
        self.client = client
        self.event: Event = Event()
        self.command_data: bytes | None = None
        self.callback = None
        self.wand_type = None
        self.serial_number = None
        self.sku = None
        self.firmware = None
        self.box_address = None
        self.manufacturer_id = None
        self.device_id = None
        self.edition = None
        self.companion_address = None

    async def is_connected(self) -> bool:
        return self.client.is_connected
    
    async def register_callbck(self, cb):
        self.callback = cb

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        await self.client.start_notify(COMMAND_UUID, self._command_handler)
        await self.client.start_notify(STREAM_UUID, self._stream_handler)
        await sleep(1.0)

    @disconnect_on_missing_services
    async def stop_notify(self) -> None:
        await self.client.stop_notify(COMMAND_UUID)

    @disconnect_on_missing_services
    async def write(self, uuid: str, data: bytes, response = False) -> None:
        _LOGGER.debug("Write UUID=%s data=%s", uuid, len(data))
        chunk = len(data)
        for i in range(0, len(data), chunk):
            await self.client.write_gatt_char(uuid, data[i : i + chunk], response)
            #await sleep(0.05)

    def _command_handler(self, _: Any, data: bytearray) -> None:
        response = Protocol.parse_response(data)
        if isinstance(response, ResponseWandType):
            self.wand_type = response
        elif isinstance(response, ResponseSerialNumber):
            self.serial_number = response
        elif isinstance(response, ResponseSKU):
            self.sku = response
        elif isinstance(response, ResponseFirmware):
            self.firmware = response
        elif isinstance(response, ResponseBoxAddress):
            self.box_address = response
        elif isinstance(response, ResponseManufacturerID):
            self.manufacturer_id = response
        elif isinstance(response, ResponseDeviceID):
            self.device_id = response
        elif isinstance(response, ResponseEdition):
            self.edition = response
        elif isinstance(response, ResponseCompanionAddress):
            self.companion_address = response
        elif response is None:
            pass           

    def _stream_handler(self, _: Any, data: bytearray) -> None:
        response = Protocol.parse_stream(data)
        if not self.callback:
            if isinstance(response, EventSpell):
                self.callback(response.name)
            elif isinstance(response, EventButton):
                if response.is_big_pressed:
                    self.callback("big")
                elif response.is_top_pressed:
                    self.callback("top")
                elif response.is_mid_pressed:
                    self.callback("mid")
                elif response.is_bot_pressed:
                    self.callback("bot")

    async def read(self, timeout: float = 5.0) -> bytes:
        await wait_for(self.event.wait(), timeout)
        data = self.command_data or b""
        _LOGGER.debug("Received: %s", data.hex())
        return data

    async def write_command(self, packet: bytes) -> bytes:
        last_exception = None
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.command_data = None
                self.event.clear()
                await self.write(COMMAND_UUID, packet, True)
                return await self.read()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    _LOGGER.warning(f"Write retry (attempt {attempt}/{max_retries})")
                    await sleep(0.5)
                    continue
                raise last_exception
            
    async def keep_alive(self) -> bytes:
        res = self.write_command(Protocol.build_keep_alive())
        return Protocol.parse_response(res)
    
    async def request_firmware(self) -> ResponseFirmware:
        res = self.write_command(Protocol.build_request_firmware())
        return Protocol.parse_response(res)

    async def request_request_box_address(self) -> ResponseBoxAddress:
        res = self.write_command(Protocol.build_request_box_address())
        return Protocol.parse_response(res)
