"""Support for Mcw sensors."""

from __future__ import annotations

from typing import cast
from functools import partial
from .mcw_ble import SensorDeviceClass as McwSensorDeviceClass, SensorUpdate, Units
from .mcw_ble.const import (
    ExtendedSensorDeviceClass as McwExtendedSensorDeviceClass,
)

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_SW_VERSION,
    ATTR_HW_VERSION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfConductivity,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .coordinator import McwPassiveBluetoothDataProcessor
from .device import device_key_to_bluetooth_entity_key
from .types import McwConfigEntry

SENSOR_DESCRIPTIONS = {
    # Acceleration (m/s²)
    (
        McwSensorDeviceClass.ACCELERATION,
        Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.ACCELERATION}_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Battery (percent)
    (McwSensorDeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Channel (-)
    (McwExtendedSensorDeviceClass.CHANNEL, None): SensorEntityDescription(
        key=str(McwExtendedSensorDeviceClass.CHANNEL),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Conductivity (µS/cm)
    (
        McwSensorDeviceClass.CONDUCTIVITY,
        Units.CONDUCTIVITY,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.CONDUCTIVITY}_{Units.CONDUCTIVITY}",
        device_class=SensorDeviceClass.CONDUCTIVITY,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Count (-)
    (McwSensorDeviceClass.COUNT, None): SensorEntityDescription(
        key=str(McwSensorDeviceClass.COUNT),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # CO2 (parts per million)
    (
        McwSensorDeviceClass.CO2,
        Units.CONCENTRATION_PARTS_PER_MILLION,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.CO2}_{Units.CONCENTRATION_PARTS_PER_MILLION}",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Current (Ampere)
    (
        McwSensorDeviceClass.CURRENT,
        Units.ELECTRIC_CURRENT_AMPERE,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.CURRENT}_{Units.ELECTRIC_CURRENT_AMPERE}",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Dew Point (°C)
    (McwSensorDeviceClass.DEW_POINT, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.DEW_POINT}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Directions (°)
    (McwExtendedSensorDeviceClass.DIRECTION, Units.DEGREE): SensorEntityDescription(
        key=f"{McwExtendedSensorDeviceClass.DIRECTION}_{Units.DEGREE}",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Distance (mm)
    (
        McwSensorDeviceClass.DISTANCE,
        Units.LENGTH_MILLIMETERS,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.DISTANCE}_{Units.LENGTH_MILLIMETERS}",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Distance (m)
    (McwSensorDeviceClass.DISTANCE, Units.LENGTH_METERS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.DISTANCE}_{Units.LENGTH_METERS}",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Duration (seconds)
    (McwSensorDeviceClass.DURATION, Units.TIME_SECONDS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.DURATION}_{Units.TIME_SECONDS}",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Energy (kWh)
    (
        McwSensorDeviceClass.ENERGY,
        Units.ENERGY_KILO_WATT_HOUR,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.ENERGY}_{Units.ENERGY_KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    # Gas (m3)
    (
        McwSensorDeviceClass.GAS,
        Units.VOLUME_CUBIC_METERS,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.GAS}_{Units.VOLUME_CUBIC_METERS}",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # Gyroscope (°/s)
    (
        McwSensorDeviceClass.GYROSCOPE,
        Units.GYROSCOPE_DEGREES_PER_SECOND,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.GYROSCOPE}_{Units.GYROSCOPE_DEGREES_PER_SECOND}",
        native_unit_of_measurement=Units.GYROSCOPE_DEGREES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Humidity in (percent)
    (McwSensorDeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Illuminance (lux)
    (McwSensorDeviceClass.ILLUMINANCE, Units.LIGHT_LUX): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.ILLUMINANCE}_{Units.LIGHT_LUX}",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass sensor (kg)
    (McwSensorDeviceClass.MASS, Units.MASS_KILOGRAMS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.MASS}_{Units.MASS_KILOGRAMS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass sensor (lb)
    (McwSensorDeviceClass.MASS, Units.MASS_POUNDS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.MASS}_{Units.MASS_POUNDS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Moisture (percent)
    (McwSensorDeviceClass.MOISTURE, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.MOISTURE}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Packet Id (-)
    (McwSensorDeviceClass.PACKET_ID, None): SensorEntityDescription(
        key=str(McwSensorDeviceClass.PACKET_ID),
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # PM10 (µg/m3)
    (
        McwSensorDeviceClass.PM10,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.PM10}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # PM2.5 (µg/m3)
    (
        McwSensorDeviceClass.PM25,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.PM25}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Power (Watt)
    (McwSensorDeviceClass.POWER, Units.POWER_WATT): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.POWER}_{Units.POWER_WATT}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Precipitation (mm)
    (
        McwExtendedSensorDeviceClass.PRECIPITATION,
        Units.LENGTH_MILLIMETERS,
    ): SensorEntityDescription(
        key=f"{McwExtendedSensorDeviceClass.PRECIPITATION}_{Units.LENGTH_MILLIMETERS}",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Pressure (mbar)
    (McwSensorDeviceClass.PRESSURE, Units.PRESSURE_MBAR): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.PRESSURE}_{Units.PRESSURE_MBAR}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Raw (-)
    (McwExtendedSensorDeviceClass.RAW, None): SensorEntityDescription(
        key=str(McwExtendedSensorDeviceClass.RAW),
    ),
    # Rotation (°)
    (McwSensorDeviceClass.ROTATION, Units.DEGREE): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.ROTATION}_{Units.DEGREE}",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Signal Strength (RSSI) (dB)
    (
        McwSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Speed (m/s)
    (
        McwSensorDeviceClass.SPEED,
        Units.SPEED_METERS_PER_SECOND,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.SPEED}_{Units.SPEED_METERS_PER_SECOND}",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Temperature (°C)
    (McwSensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Text (-)
    (McwExtendedSensorDeviceClass.TEXT, None): SensorEntityDescription(
        key=str(McwExtendedSensorDeviceClass.TEXT),
    ),
    # Timestamp (datetime object)
    (
        McwSensorDeviceClass.TIMESTAMP,
        None,
    ): SensorEntityDescription(
        key=str(McwSensorDeviceClass.TIMESTAMP),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    # UV index (-)
    (
        McwSensorDeviceClass.UV_INDEX,
        None,
    ): SensorEntityDescription(
        key=str(McwSensorDeviceClass.UV_INDEX),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volatile organic Compounds (VOC) (µg/m3)
    (
        McwSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Voltage (volt)
    (
        McwSensorDeviceClass.VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_VOLT}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volume (L)
    (
        McwSensorDeviceClass.VOLUME,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.VOLUME}_{Units.VOLUME_LITERS}",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # Volume (mL)
    (
        McwSensorDeviceClass.VOLUME,
        Units.VOLUME_MILLILITERS,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.VOLUME}_{Units.VOLUME_MILLILITERS}",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # Volume Flow Rate (m3/hour)
    (
        McwSensorDeviceClass.VOLUME_FLOW_RATE,
        Units.VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.VOLUME_FLOW_RATE}_{Units.VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR}",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volume Storage (L)
    (
        McwExtendedSensorDeviceClass.VOLUME_STORAGE,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=f"{McwExtendedSensorDeviceClass.VOLUME_STORAGE}_{Units.VOLUME_LITERS}",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Water (L)
    (
        McwSensorDeviceClass.WATER,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.WATER}_{Units.VOLUME_LITERS}",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # # TVOC (µg/m3)
    # (
    #     McwSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    #     Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    # ): SensorEntityDescription(
    #     key=f"{McwSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
    #     device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    #     native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
    # HCHO (µg/m3)
    (
        McwSensorDeviceClass.FORMALDEHYDE,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{McwSensorDeviceClass.FORMALDEHYDE}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

def hass_device_info(sensor_device_info):
    device_info = sensor_device_info_to_hass_device_info(sensor_device_info)
    if sensor_device_info.sw_version is not None:
        device_info[ATTR_SW_VERSION] = sensor_device_info.sw_version
    if sensor_device_info.hw_version is not None:
        device_info[ATTR_HW_VERSION] = sensor_device_info.hw_version
    return device_info
    
def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[float | None]:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                (description.device_class, description.native_unit_of_measurement)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.device_class
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): cast(
                float | None, sensor_values.native_value
            )
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: McwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE sensors."""
    coordinator = entry.runtime_data
    processor = McwPassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            McwBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class McwBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[McwPassiveBluetoothDataProcessor[float | None]],
    SensorEntity,
):
    """Representation of a Mcw BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        poll_coordinator = self.processor.coordinator.poll_coordinator
        remove = poll_coordinator.async_add_listener(partial(self.processor.async_handle_update, poll_coordinator.data))
        self.async_on_remove(remove)