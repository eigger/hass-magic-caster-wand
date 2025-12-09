from __future__ import annotations

import logging
from typing import Any
from bleak.backends.device import BLEDevice
from bluetooth_sensor_state_data import BluetoothData
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from sensor_state_data import (
    SensorLibrary,
    SensorUpdate,
    SensorDeviceClass,
    Units,
)
from sensor_state_data.description import (
    BaseSensorDescription,
)
from .const import SERVICE_WP6003, TIMEOUT_1DAY, TIMEOUT_5MIN
from .writer import get_sensor_data

_LOGGER = logging.getLogger(__name__)

def to_mac(addr: bytes) -> str:
    """Return formatted MAC address."""
    return ":".join(f"{i:02X}" for i in addr)

TVOC__CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = BaseSensorDescription(
    device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
)
HCHO__CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = BaseSensorDescription(
    device_class=SensorDeviceClass.FORMALDEHYDE,
    native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
)
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
        if not super().supported(data):
            return False
        return True

    def _start_update(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Update from BLE advertisement data."""
        #_LOGGER.debug(f"service_info: {service_info}")
        for uuid in service_info.service_uuids:
            if uuid == SERVICE_WP6003:
                if self._parse_wp6003(service_info):
                    self.last_service_info = service_info
        return None

    def _parse_wp6003(
        self, service_info: BluetoothServiceInfoBleak
    ) -> bool:
        """Parser for Mcw sensors"""

        model = "WP6003"
        manufacturer = "Mcw Technology CO., LTD"

        identifier = service_info.address.replace(":", "")[-4:]
        self.set_title(f"{model} {identifier}")
        self.set_device_name(f"{model} {identifier}")
        self.set_device_type(f"Air Quality Monitor")
        self.set_device_manufacturer(manufacturer)
        self.pending = False
        return True
    
    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """
        Poll the device to retrieve any values we can't get from passive listening.
        """
        self._events_updates.clear()
        data = await get_sensor_data(ble_device)
        #0a0001010e02010908000065000f01000251
        if len(data) == 18:
            temperature = ((data[6] << 8) + data[7]) / 10
            tvoc = ((data[10] << 8) + data[11]) / 1000
            hcho = ((data[12] << 8) + data[13]) / 1000
            co2 = ((data[16] << 8) + data[17])
            
            self.update_predefined_sensor(SensorLibrary.TEMPERATURE__CELSIUS, round(temperature, 2))
            self.update_predefined_sensor(TVOC__CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, round(tvoc, 2))
            self.update_predefined_sensor(HCHO__CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, round(hcho, 2))
            self.update_predefined_sensor(SensorLibrary.CO2__CONCENTRATION_PARTS_PER_MILLION, co2)

        return self._finish_update()
