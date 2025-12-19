"""Support for mcw ble sensors."""

import logging
import dataclasses

from .mcw_ble import BLEData

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    # "battery": SensorEntityDescription(
    #     key="battery",
    #     device_class=SensorDeviceClass.BATTERY,
    #     native_unit_of_measurement=PERCENTAGE,
    #     name="battery",
    # ),
    # "closingstate": SensorEntityDescription(
    #     key="closingstate",
    #     name="closingstate",
    # ),
    # "powerlevel": SensorEntityDescription(
    #     key="powerlevel",
    #     name="powerlevel",
    # ),
    # "paperstate": SensorEntityDescription(
    #     key="paperstate",
    #     name="paperstate",
    # ),
    # "rfidreadstate": SensorEntityDescription(
    #     key="rfidreadstate",
    #     name="rfidreadstate",
    # ),
    # "density": SensorEntityDescription(
    #     key="density",
    #     name="density",
    # ),
    # "printspeed": SensorEntityDescription(
    #     key="printspeed",
    #     name="printspeed",
    # ),
    # "labeltype": SensorEntityDescription(
    #     key="labeltype",
    #     name="labeltype",
    # ),
    # "languagetype": SensorEntityDescription(
    #     key="languagetype",
    #     name="languagetype",
    # ),
    # "autoshutdowntime": SensorEntityDescription(
    #     key="autoshutdowntime",
    #     name="autoshutdowntime",
    # ),
    # "devicetype": SensorEntityDescription(
    #     key="devicetype",
    #     name="devicetype",
    # ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE sensors."""
    coordinator: DataUpdateCoordinator[BLEData] = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    spell_coordinator: DataUpdateCoordinator[str] = hass.data[DOMAIN][entry.entry_id]["spell_coordinator"]
    # we need to change some units
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            McwSensor(coordinator, coordinator.data, sensors_mapping[sensor_type])
        )
    entities.append(
        McwSellSensor(spell_coordinator)
    )
    async_add_entities(entities)


class McwSensor(CoordinatorEntity[DataUpdateCoordinator[BLEData]], SensorEntity):
    """Mcw BLE sensors for the device."""

    # _attr_state_class = None
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[BLEData],
        ble_data: BLEData,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the mcw entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{ble_data.name} {ble_data.identifier}"

        self._attr_unique_id = f"{name}_{entity_description.key}"

        self._id = ble_data.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    ble_data.address,
                )
            },
            name=name,
            manufacturer="Mcw",
            model=ble_data.model,
            hw_version=ble_data.hw_version,
            sw_version=ble_data.sw_version,
            serial_number=ble_data.serial_number,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        try:
            return self.coordinator.data.sensors[self.entity_description.key]
        except KeyError:
            return None

class McwSellSensor(
    CoordinatorEntity[DataUpdateCoordinator[str]], 
    SensorEntity,
):
    #_attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry, coordinator: DataUpdateCoordinator[str]):
        CoordinatorEntity.__init__(self, coordinator)
        # self.hass = hass
        address = hass.data[DOMAIN][entry.entry_id]['address']
        self._address = address
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = f"Mcw {self._identifier} Spell"
        self._attr_unique_id = f"mcw_{self._identifier}_spell"
        self._spell = ""


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
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        try:
            return str(self._spell)
        except KeyError:
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Updated binary data")
        self._spell = self.data
        super()._handle_coordinator_update()