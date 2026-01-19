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
from .mcw_ble import BLEData

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
    buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] = data["buttons_coordinator"]
    address = data["address"]
    mcw = data["mcw"]

    entities = [
        McwButtonBinarySensor(
            address=address,
            mcw=mcw,
            coordinator=buttons_coordinator,
            button_key=button["key"],
            button_name=button["name"]
        )
        for button in BUTTONS
    ]

    # Add connection status binary sensor
    coordinator = data["coordinator"]
    entities.append(McwConnectionBinarySensor(address, mcw, coordinator))

    async_add_entities(entities)


class McwButtonBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, bool]]],
    BinarySensorEntity,
):
    """Binary sensor entity for tracking wand button state."""

    _attr_has_entity_name = True
    _attr_device_class = None #BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[dict[str, bool]],
        button_key: str,
        button_name: str
    ) -> None:
        """Initialize the button binary sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._button_key = button_key
        
        self._attr_name = button_name
        self._attr_unique_id = f"mcw_{self._identifier}_{button_key}"
        self._is_on = False

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
            _LOGGER.debug(
                "Button %s state: %s", self._button_key, self._is_on
            )
        self.async_write_ha_state()


class McwConnectionBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[BLEData]],
    BinarySensorEntity,
):
    """Binary sensor entity for tracking BLE connection state."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        address: str,
        mcw,
        coordinator: DataUpdateCoordinator[BLEData],
    ) -> None:
        """Initialize the connection binary sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        
        self._attr_name = "Connected"
        self._attr_unique_id = f"mcw_{self._identifier}_connected"

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
    def is_on(self) -> bool:
        """Return true if connected."""
        return self._mcw.is_connected() if self._mcw else False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
