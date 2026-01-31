"""Support for Magic Caster Wand BLE select entity."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CASTING_LED_COLORS, DEFAULT_CASTING_LED_COLOR, DOMAIN, MANUFACTURER
from .mcw_ble import McwDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE select entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    mcw: McwDevice = data["mcw"]

    async_add_entities([McwCastingLedColorSelect(address, mcw)])


class McwCastingLedColorSelect(SelectEntity, RestoreEntity):
    """Select entity for choosing casting LED color."""

    _attr_has_entity_name = True

    def __init__(self, address: str, mcw: McwDevice) -> None:
        """Initialize the select entity."""
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Casting LED Color"
        self._attr_unique_id = f"mcw_{self._identifier}_casting_led_color"
        self._attr_icon = "mdi:palette"
        self._attr_options = list(CASTING_LED_COLORS.keys())
        self._attr_current_option = DEFAULT_CASTING_LED_COLOR

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

    def _apply_color(self) -> None:
        """Apply the current color selection to the device."""
        self._mcw.casting_led_color = CASTING_LED_COLORS.get(
            self._attr_current_option, CASTING_LED_COLORS[DEFAULT_CASTING_LED_COLOR]
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self._apply_color()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            _LOGGER.debug("Restored casting LED color: %s", last_state.state)
            self._attr_current_option = last_state.state

        # Make sure the current casting color is applied to the device
        try:
            self._apply_color()
        except Exception as err:
            _LOGGER.error("Failed to apply casting LED color: %s", err)
