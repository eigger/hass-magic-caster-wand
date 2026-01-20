"""Support for Magic Caster Wand BLE sensors."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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


# Calibration sensor definitions
CALIBRATION_SENSORS = [
    {"key": "calibration_button", "name": "Calibration Button", "icon": "mdi:gesture-tap-button"},
    {"key": "calibration_imu", "name": "Calibration IMU", "icon": "mdi:axis-arrow"},
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    spell_coordinator: DataUpdateCoordinator[str] = data["spell_coordinator"]
    battery_coordinator: DataUpdateCoordinator[float] = data["battery_coordinator"]
    calibration_coordinator: DataUpdateCoordinator[dict[str, str]] = data["calibration_coordinator"]
    address = data["address"]
    mcw = data["mcw"]

    entities = [
        McwSpellSensor(address, mcw, spell_coordinator),
        McwBatterySensor(address, mcw, battery_coordinator),
        McwSpellModeSensor(address, mcw),
    ]

    # Add calibration sensors
    for sensor in CALIBRATION_SENSORS:
        entities.append(
            McwCalibrationSensor(
                address=address,
                mcw=mcw,
                coordinator=calibration_coordinator,
                sensor_key=sensor["key"],
                sensor_name=sensor["name"],
                sensor_icon=sensor["icon"],
            )
        )

    async_add_entities(entities)


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


class McwSpellModeSensor(McwBaseSensor):
    """Sensor entity for showing spell detection mode."""

    def __init__(self, address: str, mcw) -> None:
        """Initialize the spell mode sensor."""
        McwBaseSensor.__init__(self, address, mcw)

        self._attr_name = "Spell Detection Mode"
        self._attr_unique_id = f"mcw_{self._identifier}_spell_mode"
        self._attr_icon = "mdi:auto-fix"

    @property
    def native_value(self) -> StateType:
        """Return the spell detection mode."""
        return self._mcw.spell_detection_mode if self._mcw else "Unknown"


class McwCalibrationSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, str]]],
    McwBaseSensor,
):
    """Sensor entity for tracking calibration state."""

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[dict[str, str]],
        sensor_key: str,
        sensor_name: str,
        sensor_icon: str,
    ) -> None:
        """Initialize the calibration sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        McwBaseSensor.__init__(self, address, mcw)

        self._sensor_key = sensor_key
        self._sensor_icon = sensor_icon
        self._attr_name = sensor_name
        self._attr_unique_id = f"mcw_{self._identifier}_{sensor_key}"
        self._state: str = "Pending"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._sensor_icon

    @property
    def native_value(self) -> StateType:
        """Return the calibration state."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            calibration_states = self.coordinator.data
            # Only update state if this sensor's key is present in the data
            if self._sensor_key in calibration_states:
                self._state = calibration_states[self._sensor_key]
                _LOGGER.debug(
                    "Calibration %s state: %s", self._sensor_key, self._state
                )
        self.async_write_ha_state()