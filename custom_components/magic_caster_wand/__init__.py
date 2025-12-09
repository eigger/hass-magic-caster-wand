"""The Mcw Bluetooth integration."""

from __future__ import annotations

from functools import partial
import logging
from asyncio import sleep, Lock
from .mcw_ble import McwBluetoothDeviceData, SensorUpdate
from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.util.signal_type import SignalType
from homeassistant.exceptions import HomeAssistantError
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    CONF_DISCOVERED_EVENT_CLASSES,
    DOMAIN,
    McwBleEvent,
)
from .coordinator import McwPassiveBluetoothProcessorCoordinator
from .types import McwConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

def process_service_info(
    hass: HomeAssistant,
    entry: McwConfigEntry,
    device_registry: DeviceRegistry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    coordinator = entry.runtime_data
    data = coordinator.device_data
    update = data.update(service_info)

    return update


def format_event_dispatcher_name(
    address: str, event_class: str
) -> SignalType[McwBleEvent]:
    """Format an event dispatcher name."""
    return SignalType(f"{DOMAIN}_event_{address}_{event_class}")


def format_discovered_event_class(address: str) -> SignalType[str, McwBleEvent]:
    """Format a discovered event class."""
    return SignalType(f"{DOMAIN}_discovered_event_class_{address}")


async def async_setup_entry(hass: HomeAssistant, entry: McwConfigEntry) -> bool:
    """Set up Mcw Bluetooth from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    address = entry.unique_id
    assert address is not None

    data = McwBluetoothDeviceData()
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]['address'] = address
    hass.data[DOMAIN][entry.entry_id]['data'] = data

    device_registry = dr.async_get(hass)
    event_classes = set(entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, ()))
    bt_coordinator = McwPassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=partial(process_service_info, hass, entry, device_registry),
        device_data=data,
        discovered_event_classes=event_classes,
        connectable=True,
        entry=entry,
    )

    async def _async_poll_data(hass: HomeAssistant, entry: McwConfigEntry) -> SensorUpdate:
        try:
            device = async_ble_device_from_address(hass, hass.data[DOMAIN][entry.entry_id]['address'])
            if not device:
                raise UpdateFailed("BLE Device none")
            coordinator = entry.runtime_data
            return await coordinator.device_data.async_poll(device)
        except Exception as err:
            raise UpdateFailed(f"polling error: {err}") from err

    poll_coordinator = DataUpdateCoordinator[SensorUpdate](
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=partial(_async_poll_data, hass, entry),
        update_interval=timedelta(minutes=5),
    )
    
    entry.runtime_data = bt_coordinator
    entry.runtime_data.poll_coordinator = poll_coordinator
    await poll_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(bt_coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: McwConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def get_entry_id_from_device(hass, device_id: str) -> str:
    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get(device_id)
    if not device_entry:
        raise ValueError(f"Unknown device_id: {device_id}")
    if not device_entry.config_entries:
        raise ValueError(f"No config entries for device {device_id}")

    _LOGGER.debug(f"{device_id} to {device_entry.config_entries}")
    try:
        entry_id = next(iter(device_entry.config_entries))
    except StopIteration:
        _LOGGER.error("%s None", device_id)
        return None

    return entry_id