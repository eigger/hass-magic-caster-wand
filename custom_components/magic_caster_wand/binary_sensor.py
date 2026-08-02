"""Support for Magic Caster Wand BLE button binary sensors."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER
from .mcw_ble import McbDevice, McwDevice

_LOGGER = logging.getLogger(__name__)

# Button definitions with key, name, and icon
BUTTONS = [
    {"key": "button_1", "name": "Button 1"},
    {"key": "button_2", "name": "Button 2"},
    {"key": "button_3", "name": "Button 3"},
    {"key": "button_4", "name": "Button 4"},
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE button binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    device = data["device"]
    device_type = data["type"]
    connection_coordinator: DataUpdateCoordinator[bool] = data["connection_coordinator"]

    entities = []
    if device_type == "mcw":
        buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] = data["buttons_coordinator"]
        entities.extend(
            [
                McwButtonBinarySensor(
                    address=address,
                    mcw=device,
                    coordinator=buttons_coordinator,
                    connection_coordinator=connection_coordinator,
                    button_key=button["key"],
                    button_name=button["name"],
                )
                for button in BUTTONS
            ]
        )

    elif device_type == "mcb":
        entities.extend(
            [
                McbLidBinarySensor(address, device, data["lid_coordinator"], connection_coordinator),
                McbUSBPluggedBinarySensor(address, device, data["usb_plugged_coordinator"], connection_coordinator),
                McbWandPresentBinarySensor(address, device, data["wand_coordinator"], connection_coordinator),
            ]
        )

    # Add connection status binary sensor
    entities.append(McwConnectionBinarySensor(address, device, connection_coordinator))

    async_add_entities(entities)


class McwButtonBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, bool]]],
    BinarySensorEntity,
):
    """Binary sensor entity for tracking wand button state."""

    _attr_has_entity_name = True
    _attr_device_class = None  # BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[dict[str, bool]],
        connection_coordinator: DataUpdateCoordinator[bool],
        button_key: str,
        button_name: str,
    ) -> None:
        """Initialize the button binary sensor."""
        CoordinatorEntity.__init__(self, coordinator)

        self._address = address
        self._mcw = mcw
        self._connection_coordinator = connection_coordinator
        self._identifier = address.replace(":", "")[-8:]
        self._button_key = button_key

        self._attr_name = button_name
        self._attr_unique_id = f"mcw_{self._identifier}_{button_key}"
        self._is_on = False

    async def async_added_to_hass(self) -> None:
        """Register connection coordinator listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self._connection_coordinator.async_add_listener(self._handle_connection_update))

    @callback
    def _handle_connection_update(self) -> None:
        """Handle connection state changes."""
        self.async_write_ha_state()

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
        """Return True if entity is available."""
        return self._connection_coordinator.data is True

    @property
    def is_on(self) -> bool:
        """Return true if the button is pressed."""
        return self._is_on

    @property
    def icon(self) -> str:
        """Return the icon based on button state."""
        return "mdi:radiobox-marked" if self._is_on else "mdi:radiobox-blank"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            button_states = self.coordinator.data
            self._is_on = button_states.get(self._button_key, False)
            _LOGGER.debug("Button %s state: %s", self._button_key, self._is_on)
        self.async_write_ha_state()


class McwConnectionBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[bool]],
    BinarySensorEntity,
):
    """Binary sensor entity for tracking BLE connection state."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        address: str,
        device: McwDevice | McbDevice,
        connection_coordinator: DataUpdateCoordinator[bool],
    ) -> None:
        """Initialize the connection binary sensor."""
        CoordinatorEntity.__init__(self, connection_coordinator)

        self._address = address
        self._device = device
        self._identifier = address.replace(":", "")[-8:]

        self._attr_name = "Connected"
        self._attr_unique_id = f"mcw_{self._identifier}_connected"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device_label = "Wand" if isinstance(self._device, McwDevice) else "Box"
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster {device_label} {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._device.model if self._device else None,
        )

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.data is True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class McbBaseBinarySensor(CoordinatorEntity[DataUpdateCoordinator[bool]], BinarySensorEntity):
    """Base class for Magic Caster Box binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, address, device, coordinator, connection_coordinator, name, key):
        CoordinatorEntity.__init__(self, coordinator)

        self._address = address
        self._device = device
        self._identifier = address.replace(":", "")[-8:]
        self._attr_unique_id = f"{address}_{key}"
        self._attr_name = name
        self._key = key
        self._connection_coordinator = connection_coordinator

    async def async_added_to_hass(self) -> None:
        """Register connection coordinator listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self._connection_coordinator.async_add_listener(self._handle_connection_update))

    @callback
    def _handle_connection_update(self) -> None:
        """Handle connection state changes."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Box {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._device.model if self._device else None,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._connection_coordinator.data is True

    @property
    def is_on(self) -> bool:
        """Return True if entity is true."""
        try:
            return bool(self.coordinator.data)
        except Exception as err:
            _LOGGER.error("Error reading state: %s", err)
            return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class McbLidBinarySensor(McbBaseBinarySensor):
    """Magic Caster Box lid open/close sensor."""

    def __init__(self, address, device, coordinator, connection_coordinator):
        super().__init__(
            address=address,
            device=device,
            coordinator=coordinator,
            connection_coordinator=connection_coordinator,
            name="Lid",
            key="lid",
        )


class McbUSBPluggedBinarySensor(McbBaseBinarySensor):
    """Magic Caster Box USB plugged-in sensor."""

    def __init__(self, address, device, coordinator, connection_coordinator):
        super().__init__(
            address=address,
            device=device,
            coordinator=coordinator,
            connection_coordinator=connection_coordinator,
            name="USB Plugged",
            key="usb_plugged",
        )


class McbWandPresentBinarySensor(McbBaseBinarySensor):
    """Magic Caster Box wand-present sensor."""

    def __init__(self, address, device, coordinator, connection_coordinator):
        super().__init__(
            address=address,
            device=device,
            coordinator=coordinator,
            connection_coordinator=connection_coordinator,
            name="Wand",
            key="wand_present",
        )
