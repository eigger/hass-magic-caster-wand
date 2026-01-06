"""Support for Magic Caster Wand BLE sensors."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER
from .mcw_ble import BLEData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    spell_coordinator: DataUpdateCoordinator[str] = data["spell_coordinator"]
    battery_coordinator: DataUpdateCoordinator[float] = data["battery_coordinator"]
    address = data["address"]
    mcw = data["mcw"]

    async_add_entities([
        McwSpellSensor(address, mcw, spell_coordinator),
        McwBatterySensor(address, mcw, battery_coordinator),
    ])


class McwBaseSensor(SensorEntity):
    """Base class for Magic Caster Wand sensors."""

    _attr_has_entity_name = True

    def __init__(self, address: str, mcw) -> None:
        """Initialize the base sensor."""
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._mcw.model if self._mcw else None,
        )


class McwSpellSensor(
    CoordinatorEntity[DataUpdateCoordinator[str]],
    McwBaseSensor,
):
    """Sensor entity for tracking wand spell detection."""

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[str],
    ) -> None:
        """Initialize the spell sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        McwBaseSensor.__init__(self, address, mcw)

        self._attr_name = "Spell"
        self._attr_unique_id = f"mcw_{self._identifier}_spell"
        self._attr_icon = "mdi:magic-staff"
        self._spell = "awaiting"
        self._attr_extra_state_attributes = {"last_updated": None}

    @property
    def native_value(self) -> StateType:
        """Return the current spell value."""
        return str(self._spell)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            _LOGGER.debug("Spell detected: %s", self.coordinator.data)
            self._spell = self.coordinator.data
            self._attr_extra_state_attributes["last_updated"] = dt_util.now()
        self.async_write_ha_state()


class McwBatterySensor(
    CoordinatorEntity[DataUpdateCoordinator[float]],
    McwBaseSensor,
):
    """Sensor entity for tracking wand battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[float],
    ) -> None:
        """Initialize the battery sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        McwBaseSensor.__init__(self, address, mcw)

        self._attr_name = "Battery"
        self._attr_unique_id = f"mcw_{self._identifier}_battery"
        self._battery: float = 0.0

    @property
    def native_value(self) -> StateType:
        """Return the battery level."""
        return self._battery

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is not None:
            _LOGGER.debug("Battery level: %s%%", self.coordinator.data)
            self._battery = self.coordinator.data
        self.async_write_ha_state()