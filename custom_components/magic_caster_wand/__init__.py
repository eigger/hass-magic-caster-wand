"""The Magic Caster Wand BLE integration."""

import logging
from datetime import timedelta
from functools import partial

from bleak_retry_connector import close_stale_connections_by_address
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble_common import BLEData
from .const import (
    CONF_SPELL_TIMEOUT,
    CONF_TFLITE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPELL_TIMEOUT,
    DEFAULT_TFLITE_URL,
    DOMAIN,
)
from .device_setup import create_device, create_runtime_data
from .mcb_ble import McbDevice as McbDevice
from .mcw_ble import McwDevice
from .runtime_data import MagicCasterWandConfigEntry
from .runtime_data import MagicCasterWandRuntimeData as MagicCasterWandRuntimeData
from .services import async_setup_services, async_unload_services

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: MagicCasterWandConfigEntry) -> bool:
    """Set up Magic Caster Wand BLE device from a config entry."""
    address = entry.unique_id
    device_type = entry.data.get("device_type", "mcw")
    if device_type not in ("mcw", "mcb"):
        _LOGGER.warning("Unknown device type %r; treating it as a wand", device_type)
        device_type = "mcw"
    assert address is not None

    await close_stale_connections_by_address(address)

    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        _LOGGER.warning(
            "Could not find Magic Caster Wand device with address %s during setup; continuing without initial data",
            address,
        )

    # Create device instance
    tflite_url = entry.options.get(CONF_TFLITE_URL, entry.data.get(CONF_TFLITE_URL, DEFAULT_TFLITE_URL))
    spell_timeout = entry.options.get(CONF_SPELL_TIMEOUT, entry.data.get(CONF_SPELL_TIMEOUT, DEFAULT_SPELL_TIMEOUT))
    device = create_device(device_type, address, tflite_url, spell_timeout)

    identifier = address.replace(":", "")[-8:]

    # Create coordinators with unique names for debugging
    coordinator: DataUpdateCoordinator[BLEData] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_main_{identifier}",
        update_method=partial(_async_update_method, hass, entry, device),
        update_interval=timedelta(seconds=float(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))),
    )

    battery_coordinator: DataUpdateCoordinator[float] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_battery_{identifier}",
    )

    connection_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_connection_{identifier}",
    )
    # Initialize with disconnected state
    connection_coordinator.async_set_updated_data(False)

    # Store data for platforms
    entry.runtime_data = create_runtime_data(
        hass,
        _LOGGER,
        address=address,
        identifier=identifier,
        device=device,
        coordinator=coordinator,
        battery_coordinator=battery_coordinator,
        connection_coordinator=connection_coordinator,
    )

    # Perform first refresh (best-effort). If it fails, entities will remain unavailable
    # until a later successful update.
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        _LOGGER.warning(
            "Initial update failed for %s; entities will start as unavailable: %s",
            address,
            coordinator.last_exception,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener to handle options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await async_setup_services(hass)

    return True


async def _async_update_method(hass: HomeAssistant, entry: MagicCasterWandConfigEntry, mcw: McwDevice) -> BLEData:
    """Get data from Magic Caster Wand BLE device."""
    address = entry.unique_id
    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise UpdateFailed(f"BLE device not available for address {address}")

    try:
        data = await mcw.update_device(ble_device)
    except Exception as err:
        raise UpdateFailed(f"Unable to fetch data: {err}") from err

    return data


async def async_unload_entry(hass: HomeAssistant, entry: MagicCasterWandConfigEntry) -> bool:
    """Unload a config entry."""
    mcw = entry.runtime_data.device
    await mcw.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if isinstance(mcw, McwDevice):
            await mcw.async_spell_tracker_close()
        await async_unload_services(hass, entry)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
