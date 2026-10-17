"""The Magic Caster Wand BLE integration."""

import asyncio
import logging
from datetime import timedelta
from functools import partial

from bleak_retry_connector import close_stale_connections_by_address
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common_ble import BLEData
from .const import (
    CONF_SPELL_TIMEOUT,
    CONF_TFLITE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPELL_TIMEOUT,
    DEFAULT_TFLITE_URL,
    DOMAIN,
)
from .device_setup import create_device, create_runtime_data
from .link import async_reconcile_links
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
            "Device is not in the Bluetooth cache; entities will remain unavailable until it is discovered",
        )

    # Create device instance
    tflite_url = entry.options.get(CONF_TFLITE_URL, entry.data.get(CONF_TFLITE_URL, DEFAULT_TFLITE_URL))
    spell_timeout = entry.options.get(CONF_SPELL_TIMEOUT, entry.data.get(CONF_SPELL_TIMEOUT, DEFAULT_SPELL_TIMEOUT))
    device = create_device(device_type, address, tflite_url, spell_timeout, hass)

    if isinstance(device, McbDevice):
        # Set before the first refresh: the box can connect and report its wand there.
        device.on_wand_address_changed = lambda: entry.async_create_background_task(
            hass, async_reconcile_links(hass), f"{DOMAIN}_link_{address}"
        )

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

    try:
        # Perform first refresh (best-effort). If it fails, entities will remain unavailable
        # until a later successful update.
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.warning(
                "Initial update failed; entities will recover after Bluetooth discovery and a successful update",
            )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await async_reconcile_links(hass)

        # Register update listener to handle options changes
        entry.async_on_unload(entry.add_update_listener(async_update_options))

        await async_setup_services(hass)
    except BaseException:
        # Entry setup can be cancelled after a device opened its session. Always
        # close resources, including an in-flight detector request, before HA retries.
        cleanup = hass.async_create_task(_async_cleanup_failed_setup(hass, entry, device))
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
        raise

    return True


async def _async_cleanup_failed_setup(
    hass: HomeAssistant, entry: MagicCasterWandConfigEntry, device: McwDevice | McbDevice
) -> None:
    """Remove partially forwarded entities and resources before a setup retry."""
    try:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    finally:
        try:
            await _async_close_device(device)
        finally:
            await async_unload_services(hass, entry)


async def _async_update_method(hass: HomeAssistant, entry: MagicCasterWandConfigEntry, mcw: McwDevice) -> BLEData:
    """Get data from Magic Caster Wand BLE device."""
    address = entry.unique_id
    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise UpdateFailed("Device is not in the Bluetooth cache")

    try:
        data = await mcw.update_device(ble_device)
    except Exception as err:
        raise UpdateFailed("Unable to fetch data; check Bluetooth connectivity") from err

    return data


async def async_unload_entry(hass: HomeAssistant, entry: MagicCasterWandConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await _async_close_device(entry.runtime_data.device)
    await async_unload_services(hass, entry)
    return True


async def _async_close_device(device: McwDevice | McbDevice) -> None:
    """Release the BLE session and detector even if either cleanup fails."""
    try:
        await device.disconnect()
    finally:
        if isinstance(device, McwDevice):
            await device.async_spell_tracker_close()


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
