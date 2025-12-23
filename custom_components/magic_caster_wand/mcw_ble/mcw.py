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


SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
COMMAND_UUID = "57420002-587e-48a0-974c-544d6163c577"
NOTIFY_UUID = "57420003-587e-48a0-974c-544d6163c577"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

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
        self.callback_spell = None
        self.callback_battery = None
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
    
    def register_callbck(self, spell_cb, battery_cb):
        self.callback_spell = spell_cb
        self.callback_battery = battery_cb

    @disconnect_on_missing_services
    async def start_notify(self) -> None:
        await self.client.start_notify(NOTIFY_UUID, self._handler)
        await self.client.start_notify(BATTERY_UUID, self._handlerBattery)
        await sleep(1.0)

    @disconnect_on_missing_services
    async def stop_notify(self) -> None:
        await self.client.stop_notify(NOTIFY_UUID)

    @disconnect_on_missing_services
    async def write(self, uuid: str, data: bytes, response = False) -> None:
        _LOGGER.debug("Write UUID=%s data=%s", uuid, data.hex())
        chunk = len(data)
        for i in range(0, len(data), chunk):
            await self.client.write_gatt_char(uuid, data[i : i + chunk], response)
            #await sleep(0.05)

    def _handlerBattery(self, _: Any, data: bytearray) -> None:
        _LOGGER.debug("Battery Received: %s", data.hex())
        battery = int.from_bytes(data, byteorder="little")
        if self.callback_battery:
            self.callback_battery(battery)

    def _handler(self, _: Any, data: bytearray) -> None:
        _LOGGER.debug("Received: %s", data.hex())
        if self.command_data == None:
            self.command_data = bytes(data)
            self.event.set()

        if not data or len(data) < 2:
            return
        opcode = data[0]
        if opcode == 0x24:
            try:
                if len(data) < 5: 
                    return
                spell_len = data[3]
                raw_name = data[4 : 4 + spell_len]
                spell_name = raw_name.decode('utf-8', errors='ignore').strip()
                spell_name = spell_name.replace('\x00', '').replace('_', ' ')
                if not spell_name:
                    return
                _LOGGER.debug("spell: %s", spell_name)
                _LOGGER.debug("callback: %s", self.callback_spell)
                if self.callback_spell:
                    self.callback_spell(spell_name)   

            except Exception as e:
                print(f"Spell Parse Error: {e}")
                return       

    async def read(self, timeout: float = 5.0) -> bytes:
        await wait_for(self.event.wait(), timeout)
        data = self.command_data or b""
        return data

    async def write_command(self, packet: bytes, response: bool = True) -> bytes:
        last_exception = None
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if response:
                    self.command_data = None
                    self.event.clear()
                    await self.write(COMMAND_UUID, packet, False)
                    return await self.read()
                else:
                    await self.write(COMMAND_UUID, packet, False)
                    return b""
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    _LOGGER.warning(f"Write retry (attempt {attempt}/{max_retries})")
                    await sleep(0.5)
                    continue
                raise last_exception
            
    async def init_wand(self):
        await self.write_command(struct.pack('BBB', 0xdc, 0x00, 0x05), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x01, 0x05), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x02, 0x05), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x03, 0x05), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x04, 0x08), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x05, 0x08), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x06, 0x08), False)
        await self.write_command(struct.pack('BBB', 0xdc, 0x07, 0x08), False)

    async def keep_alive(self) -> bytes:
        await self.write_command(struct.pack('B', 0x01), False)

    async def get_wand_address(self) -> str:
        data = await self.write_command(struct.pack('B', 0x08), True)
        if len(data) < 7:
            return ""
        mac_le = data[1:7]          # little-endian order
        mac_be = mac_le[::-1]       # reverse
        return ":".join(f"{b:02X}" for b in mac_be)

    async def get_box_address(self) -> str:
        data = await self.write_command(struct.pack('B', 0x09), True)
        if len(data) < 7:
            return ""
        mac_le = data[1:7]          # little-endian order
        mac_be = mac_le[::-1]       # reverse
        return ":".join(f"{b:02X}" for b in mac_be)


    # await write(wand, struct.pack('BB', 0x0e, 0x01))    #Serial No
    # await write(wand, struct.pack('BB', 0x0e, 0x02))    #SKU
    # await write(wand, struct.pack('BB', 0x0e, 0x04))    #Wand No
    # await write(wand, struct.pack('BB', 0x0e, 0x09))
    async def get_wand_no(self) -> str:
        data = await self.write_command(struct.pack('BB', 0x0e, 0x04), True)
        if len(data) < 3:
            return ""
        return data[2:].decode("ascii")