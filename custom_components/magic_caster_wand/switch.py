"""Support for Magic Caster Wand BLE switch."""

import logging

from homeassistant.components import bluetooth
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER, SIGNAL_SPELL_MODE_CHANGED
from .mcw_ble import BLEData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE switch."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    mcw = data["mcw"]
    coordinator = data["coordinator"]

    async_add_entities([
        McwConnectionSwitch(hass, address, mcw, coordinator),
        McwSpellTrackingSwitch(hass, address, mcw, coordinator)
    ])


class McwConnectionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling BLE connection."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        hass: HomeAssistant, 
        address: str, 
        mcw, 
        coordinator: DataUpdateCoordinator[BLEData]
    ) -> None:
        """Initialize the connection switch."""
        super().__init__(coordinator)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Connect"
        self._attr_unique_id = f"mcw_{self._identifier}_connect"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return self._mcw.is_connected()

    @property
    def icon(self) -> str:
        """Return the icon based on connection state."""
        return "mdi:bluetooth" if self.is_on else "mdi:bluetooth-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Connect to the device."""
        ble_device = bluetooth.async_ble_device_from_address(self._hass, self._address)
        if ble_device and self._mcw:
            await self._mcw.connect(ble_device)
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disconnect from the device."""
        if self._mcw:
            await self._mcw.disconnect()
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()


class McwSpellTrackingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling IMU streaming for spell tracking."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        hass: HomeAssistant, 
        address: str, 
        mcw, 
        coordinator: DataUpdateCoordinator[BLEData]
    ) -> None:
        """Initialize the spell tracking switch."""
        super().__init__(coordinator)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Spell Tracking"
        self._attr_unique_id = f"mcw_{self._identifier}_spell_tracking"
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster Wand {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def is_on(self) -> bool:
        """Return true if IMU streaming is active."""
        if not self._mcw.is_connected():
            return False
        return self._is_on

    @property
    def icon(self) -> str:
        """Return the icon based on tracking state."""
        return "mdi:broadcast" if self.is_on else "mdi:broadcast-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Start IMU streaming."""
        if self._mcw and self._mcw.is_connected():
            await self._mcw.async_spell_tracker_init()
            await self._mcw.imu_streaming_start()
            self._is_on = True
            async_dispatcher_send(self._hass, SIGNAL_SPELL_MODE_CHANGED)
            self.async_write_ha_state()
        elif not self._mcw.is_connected():
            _LOGGER.warning("Cannot start tracking: Magic Caster Wand is not connected")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop IMU streaming."""
        if self._mcw:
            if self._mcw.is_connected():
                await self._mcw.imu_streaming_stop()
                await self._mcw.async_spell_tracker_close()
            self._is_on = False
            async_dispatcher_send(self._hass, SIGNAL_SPELL_MODE_CHANGED)
            self.async_write_ha_state()
