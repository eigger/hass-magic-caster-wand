"""The Magic Caster Wand BLE integration."""

import logging
from datetime import timedelta
from functools import partial

from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .mcw_ble import BLEData, McwDevice, LedGroup, SpellMacros

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.TEXT, Platform.BINARY_SENSOR, Platform.BUTTON]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Magic Caster Wand BLE device from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = entry.unique_id
    assert address is not None

    await close_stale_connections_by_address(address)

    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Magic Caster Wand device with address {address}"
        )

    # Create device instance
    mcw = McwDevice(address)
    identifier = address.replace(":", "")[-8:]

    # Create coordinators with unique names for debugging
    coordinator: DataUpdateCoordinator[BLEData] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_main_{identifier}",
        update_method=partial(_async_update_method, hass, entry, mcw),
        update_interval=timedelta(
            seconds=float(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        ),
    )

    spell_coordinator: DataUpdateCoordinator[str] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_spell_{identifier}",
    )

    battery_coordinator: DataUpdateCoordinator[float] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_battery_{identifier}",
    )

    buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_buttons_{identifier}",
    )

    # Register coordinators with device for BLE callbacks
    mcw.register_coordinator(spell_coordinator, battery_coordinator, buttons_coordinator)

    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()

    # Store data for platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "address": address,
        "mcw": mcw,
        "coordinator": coordinator,
        "spell_coordinator": spell_coordinator,
        "battery_coordinator": battery_coordinator,
        "buttons_coordinator": buttons_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_vibrate(call: ServiceCall) -> None:
        """Handle execution of vibrate service."""
        duration = call.data.get("duration", 500)
        for device_id in call.data.get("device_id", []):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice = hass.data[DOMAIN][entry_id]["mcw"]
                await device.buzz(duration)

    async def handle_set_led(call: ServiceCall) -> None:
        """Handle execution of set_led service."""
        group_str = call.data.get("group", "TIP")
        group = LedGroup[group_str]
        rgb = call.data.get("rgb_color", (255, 255, 255))
        duration = call.data.get("duration", 0)
        for device_id in call.data.get("device_id", []):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice = hass.data[DOMAIN][entry_id]["mcw"]
                await device.set_led(group, rgb[0], rgb[1], rgb[2], duration)

    async def handle_clear_leds(call: ServiceCall) -> None:
        """Handle execution of clear_leds service."""
        for device_id in call.data.get("device_id", []):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice = hass.data[DOMAIN][entry_id]["mcw"]
                await device.clear_leds()

    async def handle_play_spell(call: ServiceCall) -> None:
        """Handle execution of play_spell service."""
        spell_name = call.data.get("spell")
        for device_id in call.data.get("device_id", []):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice = hass.data[DOMAIN][entry_id]["mcw"]
                # Use helper for more robust spell matching
                from .mcw_ble import get_spell_macro
                macro = get_spell_macro(spell_name)
                if macro:
                    await device.send_macro(macro)

    if not hass.services.has_service(DOMAIN, "vibrate"):
        hass.services.async_register(DOMAIN, "vibrate", handle_vibrate)
    if not hass.services.has_service(DOMAIN, "set_led"):
        hass.services.async_register(DOMAIN, "set_led", handle_set_led)
    if not hass.services.has_service(DOMAIN, "clear_leds"):
        hass.services.async_register(DOMAIN, "clear_leds", handle_clear_leds)
    if not hass.services.has_service(DOMAIN, "play_spell"):
        hass.services.async_register(DOMAIN, "play_spell", handle_play_spell)

    return True


async def _async_update_method(
    hass: HomeAssistant, entry: ConfigEntry, mcw: McwDevice
) -> BLEData:
    """Get data from Magic Caster Wand BLE device."""
    address = entry.unique_id
    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if ble_device is None:
        raise UpdateFailed(f"BLE device could not be obtained from address {address}")

    try:
        data = await mcw.update_device(ble_device)
    except Exception as err:
        raise UpdateFailed(f"Unable to fetch data: {err}") from err

    return data


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    mcw: McwDevice = hass.data[DOMAIN][entry.entry_id]["mcw"]
    await mcw.disconnect()

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

    _LOGGER.debug("%s to %s", device_id, device_entry.config_entries)
    try:
        entry_id = next(iter(device_entry.config_entries))
    except StopIteration:
        _LOGGER.error("%s None", device_id)
        return None

    return entry_id
