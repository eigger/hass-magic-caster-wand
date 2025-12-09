"""Support for Mcw binary sensors."""

from __future__ import annotations

from .mcw_ble import (
    BinarySensorDeviceClass as McwBinarySensorDeviceClass,
    SensorUpdate,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .coordinator import McwPassiveBluetoothDataProcessor
from .device import device_key_to_bluetooth_entity_key
from .types import McwConfigEntry

BINARY_SENSOR_DESCRIPTIONS = {
    McwBinarySensorDeviceClass.BATTERY: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    McwBinarySensorDeviceClass.BATTERY_CHARGING: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    McwBinarySensorDeviceClass.CO: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.CO,
        device_class=BinarySensorDeviceClass.CO,
    ),
    McwBinarySensorDeviceClass.COLD: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.COLD,
        device_class=BinarySensorDeviceClass.COLD,
    ),
    McwBinarySensorDeviceClass.CONNECTIVITY: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.CONNECTIVITY,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    McwBinarySensorDeviceClass.DOOR: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    McwBinarySensorDeviceClass.HEAT: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.HEAT,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    McwBinarySensorDeviceClass.GARAGE_DOOR: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.GARAGE_DOOR,
        device_class=BinarySensorDeviceClass.GARAGE_DOOR,
    ),
    McwBinarySensorDeviceClass.GAS: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.GAS,
        device_class=BinarySensorDeviceClass.GAS,
    ),
    McwBinarySensorDeviceClass.GENERIC: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.GENERIC,
    ),
    McwBinarySensorDeviceClass.LIGHT: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.LIGHT,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    McwBinarySensorDeviceClass.LOCK: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.LOCK,
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    McwBinarySensorDeviceClass.MOISTURE: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.MOISTURE,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    McwBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    McwBinarySensorDeviceClass.MOVING: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.MOVING,
        device_class=BinarySensorDeviceClass.MOVING,
    ),
    McwBinarySensorDeviceClass.OCCUPANCY: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.OCCUPANCY,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    McwBinarySensorDeviceClass.OPENING: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.OPENING,
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    McwBinarySensorDeviceClass.PLUG: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.PLUG,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    McwBinarySensorDeviceClass.POWER: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.POWER,
        device_class=BinarySensorDeviceClass.POWER,
    ),
    McwBinarySensorDeviceClass.PRESENCE: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.PRESENCE,
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    McwBinarySensorDeviceClass.PROBLEM: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.PROBLEM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    McwBinarySensorDeviceClass.RUNNING: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    McwBinarySensorDeviceClass.SAFETY: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.SAFETY,
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    McwBinarySensorDeviceClass.SMOKE: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.SMOKE,
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    McwBinarySensorDeviceClass.SOUND: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.SOUND,
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    McwBinarySensorDeviceClass.TAMPER: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    McwBinarySensorDeviceClass.VIBRATION: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.VIBRATION,
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    McwBinarySensorDeviceClass.WINDOW: BinarySensorEntityDescription(
        key=McwBinarySensorDeviceClass.WINDOW,
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[bool | None]:
    """Convert a binary sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): BINARY_SENSOR_DESCRIPTIONS[
                description.device_class
            ]
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if description.device_class
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: McwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE binary sensors."""
    coordinator = entry.runtime_data
    processor = McwPassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            McwBluetoothBinarySensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, BinarySensorEntityDescription)
    )


class McwBluetoothBinarySensorEntity(
    PassiveBluetoothProcessorEntity[McwPassiveBluetoothDataProcessor[bool | None]],
    BinarySensorEntity,
):
    """Representation of a Mcw binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available
