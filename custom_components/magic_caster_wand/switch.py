"""Support for Magic Caster Wand BLE switch."""

import logging

from homeassistant.components import bluetooth
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER, SIGNAL_SPELL_MODE_CHANGED
from .mcw_ble import McbDevice, McwDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Caster Wand BLE switch."""
    data = hass.data[DOMAIN][entry.entry_id]
    address = data["address"]
    device = data["device"]
    device_type = data["type"]
    connection_coordinator = data["connection_coordinator"]

    entities = []
    entities.append(McwConnectionSwitch(hass, address, device, connection_coordinator))
    if device_type == "mcw":
        entities.append(McwSpellTrackingSwitch(hass, address, device, connection_coordinator))
    async_add_entities(entities)


class McwConnectionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling BLE connection."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        device: McwDevice | McbDevice,
        connection_coordinator: DataUpdateCoordinator[bool],
    ) -> None:
        """Initialize the connection switch."""
        super().__init__(connection_coordinator)
        self._hass = hass
        self._address = address
        self._device = device
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Connect"
        self._attr_unique_id = f"mcw_{self._identifier}_connect"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Only available if we have received initial data and device model is known
        return super().available and self._device is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device_label = "Wand" if isinstance(self._device, McwDevice) else "Box"
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"Magic Caster {device_label} {self._identifier}",
            manufacturer=MANUFACTURER,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return self.coordinator.data is True

    @property
    def icon(self) -> str:
        """Return the icon based on connection state."""
        return "mdi:bluetooth" if self.is_on else "mdi:bluetooth-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Connect to the device."""
        ble_device = bluetooth.async_ble_device_from_address(self._hass, self._address)
        if ble_device and self._device:
            await self._device.connect(ble_device)

    async def async_turn_off(self, **kwargs) -> None:
        """Disconnect from the device."""
        if self._device:
            await self._device.disconnect()


class McwSpellTrackingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling IMU streaming for spell tracking."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        mcw,
        connection_coordinator: DataUpdateCoordinator[bool],
    ) -> None:
        """Initialize the spell tracking switch."""
        super().__init__(connection_coordinator)
        self._hass = hass
        self._address = address
        self._mcw = mcw
        self._identifier = address.replace(":", "")[-8:]
        self._attr_name = "Spell Tracking"
        self._attr_unique_id = f"mcw_{self._identifier}_spell_tracking"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is True

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
        """Return true if spell tracking is actually running.

        Read from the device rather than tracked here, so the switch cannot report
        "on" while no IMU samples are arriving -- if a reconnect fails to re-arm
        streaming, this goes off and tells the user there is something to fix.
        """
        if self.coordinator.data is not True or not self._mcw:
            return False
        return self._mcw.spell_tracking_active

    @property
    def icon(self) -> str:
        """Return the icon based on tracking state."""
        return "mdi:broadcast" if self.is_on else "mdi:broadcast-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Start IMU streaming."""
        if self._mcw and self.coordinator.data is True:
            await self._mcw.async_spell_tracker_init()
            try:
                await self._mcw.imu_streaming_start()
            except Exception as err:
                # is_on reads the device, so it already reports off; say why.
                _LOGGER.error("Failed to start spell tracking: %s", err)
            async_dispatcher_send(self._hass, SIGNAL_SPELL_MODE_CHANGED)
            self.async_write_ha_state()
        elif self.coordinator.data is not True:
            _LOGGER.warning("Cannot start tracking: Magic Caster Wand is not connected")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop IMU streaming."""
        if self._mcw:
            if self.coordinator.data is True:
                await self._mcw.imu_streaming_stop()
            # Closing the tracker session is what clears the tracking state, so it
            # must happen even while disconnected -- otherwise the switch would stay
            # on and the next connect would re-arm streaming the user just stopped.
            await self._mcw.async_spell_tracker_close()
            async_dispatcher_send(self._hass, SIGNAL_SPELL_MODE_CHANGED)
            self.async_write_ha_state()
