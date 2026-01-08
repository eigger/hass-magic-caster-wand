"""Support for Magic Caster Wand BLE buttons."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    """Set up the Magic Caster Wand BLE buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    mcw = data["mcw"]
    coordinator = data["coordinator"]

    async_add_entities([
        McwCalibrationButton(address, mcw, coordinator),
    ])


class McwCalibrationButton(CoordinatorEntity[DataUpdateCoordinator[BLEData]], ButtonEntity):
    """Button entity for wand calibration."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        address: str, 
        mcw,
        coordinator: DataUpdateCoordinator[BLEData],
    ) -> None:
        """Initialize the calibration button."""
        super().__init__(coordinator)
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]

        self._attr_name = "Calibration"
        self._attr_unique_id = f"mcw_{self._identifier}_calibration"
        self._attr_icon = "mdi:compass-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._mcw.model if self._mcw else None,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available (device is connected)."""
        return self._mcw.is_connected() if self._mcw else False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Calibration button pressed, sending calibration packets")
        if self._mcw and self._mcw.is_connected():
            await self._mcw.calibration()
        
        _LOGGER.debug("Calibration packets sent")
