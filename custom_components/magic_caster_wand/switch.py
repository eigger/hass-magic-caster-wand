"""Support for Magic Caster Wand BLE switch."""

import logging

from homeassistant.components import bluetooth
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER
from .mcw_ble import BLEData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE switch."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    mcw = data["mcw"]
    coordinator = data["coordinator"]

    async_add_entities([McwConnectionSwitch(hass, address, mcw, coordinator)])


class McwConnectionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling BLE connection."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        hass: HomeAssistant, 
        address: str, 
        mcw, 
        coordinator: DataUpdateCoordinator[BLEData]
    ) -> None:
        """Initialize the connection switch."""
        super().__init__(coordinator)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Connection"
        self._attr_unique_id = f"mcw_{self._identifier}_connect"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return self._mcw.is_connected()

    @property
    def icon(self) -> str:
        """Return the icon based on connection state."""
        return "mdi:bluetooth" if self.is_on else "mdi:bluetooth-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Connect to the device."""
        ble_device = bluetooth.async_ble_device_from_address(self._hass, self._address)
        if ble_device and self._mcw:
            await self._mcw.connect(ble_device)

    async def async_turn_off(self, **kwargs) -> None:
        """Disconnect from the device."""
        if self._mcw:
            await self._mcw.disconnect()
