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
    calibration_coordinator = data["calibration_coordinator"]

    async_add_entities([
        McwButtonCalibration(address, mcw, coordinator, calibration_coordinator),
        McwImuCalibration(address, mcw, coordinator, calibration_coordinator),
    ])


class McwBaseCalibrationButton(CoordinatorEntity[DataUpdateCoordinator[BLEData]], ButtonEntity):
    """Base class for wand calibration buttons."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        address: str, 
        mcw,
        coordinator: DataUpdateCoordinator[BLEData],
        calibration_coordinator: DataUpdateCoordinator[dict[str, str]],
    ) -> None:
        """Initialize the calibration button."""
        super().__init__(coordinator)
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._calibration_coordinator = calibration_coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._mcw.model if self._mcw else None,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class McwButtonCalibration(McwBaseCalibrationButton):
    """Button entity for wand button calibration."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._attr_name = "Calibration Button"
        self._attr_unique_id = f"mcw_{self._identifier}_calibration_button"
        self._attr_icon = "mdi:gesture-tap-button"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Button calibration pressed")
        self._calibration_coordinator.async_set_updated_data({
            "calibration_button": "Pending",
        })
        await self._mcw.send_button_calibration()


class McwImuCalibration(McwBaseCalibrationButton):
    """Button entity for wand IMU calibration."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._attr_name = "Calibration IMU"
        self._attr_unique_id = f"mcw_{self._identifier}_calibration_imu"
        self._attr_icon = "mdi:compass-outline"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("IMU calibration pressed")
        self._calibration_coordinator.async_set_updated_data({
            "calibration_imu": "Pending",
        })
        await self._mcw.send_imu_calibration()
