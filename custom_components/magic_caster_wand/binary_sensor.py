"""Support for mcw ble binary sensors."""

import logging

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE binary sensors."""
    button_coordinator: DataUpdateCoordinator[dict] = hass.data[DOMAIN][entry.entry_id]["button_coordinator"]
    address = hass.data[DOMAIN][entry.entry_id]['address']
    mcw = hass.data[DOMAIN][entry.entry_id]['mcw']
    identifier = address.replace(":", "")[-8:]

    entities = [
        McwButtonSensor(button_coordinator, address, mcw, identifier, 1, "pad1"),
        McwButtonSensor(button_coordinator, address, mcw, identifier, 2, "pad2"),
        McwButtonSensor(button_coordinator, address, mcw, identifier, 3, "pad3"),
        McwButtonSensor(button_coordinator, address, mcw, identifier, 4, "pad4"),
    ]
    async_add_entities(entities)


class McwButtonSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict]],
    BinarySensorEntity,
):
    """Binary sensor for wand button pad state."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict],
        address: str,
        mcw,
        identifier: str,
        pad_number: int,
        pad_key: str,
    ):
        """Initialize the binary sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        self._address = address
        self._mcw = mcw
        self._identifier = identifier
        self._pad_number = pad_number
        self._pad_key = pad_key
        self._attr_name = f"Mcw {self._identifier} Button Pad {pad_number}"
        self._attr_unique_id = f"mcw_{self._identifier}_button_pad_{pad_number}"
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    self._address,
                )
            },
            name=f"Mcw {self._identifier}",
            manufacturer=MANUFACTURER,
            model=self._mcw.model if self._mcw is not None else None
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        if self._is_on:
            return "mdi:gesture-tap"
        return "mdi:circle-outline"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is available only when wand is connected
        return self._mcw.is_connected()

    @property
    def is_on(self) -> bool:
        """Return true if the button pad is touched."""
        # If not connected, always return False
        if not self.available:
            return False
        return self._is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._is_on = self.coordinator.data.get(self._pad_key, False)
            _LOGGER.debug("Button pad %d state: %s", self._pad_number, self._is_on)
        else:
            # Reset to off when no data (e.g., disconnected)
            self._is_on = False
        super()._handle_coordinator_update()
