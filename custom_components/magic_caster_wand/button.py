"""Support for mcw ble buttons."""

import logging

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mcw BLE buttons."""
    address = hass.data[DOMAIN][entry.entry_id]['address']
    mcw = hass.data[DOMAIN][entry.entry_id]['mcw']
    identifier = address.replace(":", "")[-8:]

    entities = [
        McwCalibrateButtonBaselineButton(address, mcw, identifier),
    ]
    async_add_entities(entities)


class McwCalibrateButtonBaselineButton(ButtonEntity):
    """Button to trigger capacitive button baseline calibration."""

    def __init__(self, address: str, mcw, identifier: str):
        """Initialize the button."""
        self._address = address
        self._mcw = mcw
        self._identifier = identifier
        self._attr_name = f"Mcw {self._identifier} Calibrate Button Baseline"
        self._attr_unique_id = f"mcw_{self._identifier}_calibrate_button_baseline"

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
        return "mdi:tune-vertical"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Calibrating button baseline for wand %s", self._identifier)
        try:
            # Ensure we're connected
            if not self._mcw.is_connected():
                _LOGGER.error("Cannot calibrate: wand is not connected")
                return

            # Call the calibration method from the MCW client
            await self._mcw._mcw.calibrate_button_baseline()
            _LOGGER.info("Button baseline calibration completed for wand %s", self._identifier)
        except Exception as e:
            _LOGGER.error("Failed to calibrate button baseline: %s", e)
