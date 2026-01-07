"""Support for Magic Caster Wand BLE text entity."""

import logging

from homeassistant.components.text import RestoreText
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE text entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]

    async_add_entities([McwAliasTextEntity(address)])


class McwAliasTextEntity(RestoreText):
    """Text entity for setting wand alias."""

    _attr_has_entity_name = True

    def __init__(self, address: str) -> None:
        """Initialize the text entity."""
        self._address = address
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Alias"
        self._attr_unique_id = f"mcw_{self._identifier}_alias"
        self._attr_native_max = 32
        self._attr_native_min = 0
        self._attr_mode = "text"
        self._attr_native_value = self._identifier

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        if (last_text_data := await self.async_get_last_text_data()) is None:
            return

        _LOGGER.debug("Restored state: %s", last_text_data)
        self._attr_native_max = last_text_data.native_max
        self._attr_native_min = last_text_data.native_min
        self._attr_native_value = last_text_data.native_value