"""The Mcw BLE integration."""

import logging

from functools import partial
from datetime import timedelta
from .mcw_ble import McwDevice, BLEData
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from bleak_retry_connector import close_stale_connections_by_address
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mcw BLE device from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    address = entry.unique_id
    assert address is not None

    mcw = McwDevice(address)
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]['address'] = address
    hass.data[DOMAIN][entry.entry_id]['mcw'] = mcw
    

    scan_interval = float(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    await close_stale_connections_by_address(address)

    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Mcw device with address {address}"
        )

    async def _async_update_method(hass: HomeAssistant, entry: ConfigEntry) -> BLEData:
        """Get data from Mcw BLE."""
        address = hass.data[DOMAIN][entry.entry_id]['address']
        mcw = hass.data[DOMAIN][entry.entry_id]['mcw']
        ble_device = bluetooth.async_ble_device_from_address(hass, address)
        if ble_device is None:
            raise UpdateFailed(
                f"BLE device could not be obtained from address {address}"
            )

        try:
            data = await mcw.update_device(ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=partial(_async_update_method, hass, entry),
        update_interval=timedelta(seconds=scan_interval),
    )
    spell_coordinator: DataUpdateCoordinator[str] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
    )
    mcw.register_coordinator(spell_coordinator)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id]['coordinator'] = coordinator
    hass.data[DOMAIN][entry.entry_id]['spell_coordinator'] = spell_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    # callback for the draw custom service
    async def vibrateservice(service: ServiceCall) -> ServiceResponse:
        device_ids = service.data.get("device_id")
        if isinstance(device_ids, str):
            device_ids = [device_ids]

        # Process each device
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            address = hass.data[DOMAIN][entry_id]['address']
            data = hass.data[DOMAIN][entry_id]['data']

    # register the services
    hass.services.async_register(
        DOMAIN, "vibrate", vibrateservice, supports_response=SupportsResponse.OPTIONAL
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

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