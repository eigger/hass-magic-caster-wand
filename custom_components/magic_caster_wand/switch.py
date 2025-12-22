"""Support for mcw ble switchs."""

import logging

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.switch import (
    SwitchEntity
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE switchs."""
    entities = []
    entities.append(
        McwBleSwitch(hass, entry)
    )
    async_add_entities(entities)


class McwBleSwitch(
    SwitchEntity,
):
    #_attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry):
        # self.hass = hass
        address = hass.data[DOMAIN][entry.entry_id]['address']
        self._hass = hass
        self._mcw = hass.data[DOMAIN][entry.entry_id]['mcw']
        self._address = address
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = f"Mcw {self._identifier} Connect"
        self._attr_unique_id = f"mcw_{self._identifier}_connect"


    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo (
            connections = {
                (
                    CONNECTION_BLUETOOTH,
                    self._address,
                )
            },
            name = f"Mcw {self._identifier}",
            manufacturer = "Mcw",
        )
    
    @property
    def is_on(self) -> bool | None:
        return self._mcw.is_connected()

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        if self.is_on:
            return "mdi:bluetooth" 
        return "mdi:bluetooth-off"
        
    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        ble_device = bluetooth.async_ble_device_from_address(self._hass, self._address)
        if ble_device:
            await self._mcw.connect(ble_device)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._mcw.disconnect()