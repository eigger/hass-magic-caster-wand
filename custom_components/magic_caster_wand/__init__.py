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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SPELL_TIMEOUT,
    CONF_TFLITE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPELL_TIMEOUT,
    DEFAULT_TFLITE_URL,
    DOMAIN,
)
from .mcw_ble import BLEData, McbDevice, McwDevice, resolve_led_group

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

# Registered once for the whole integration, removed when the last entry unloads.
SERVICES = ("vibrate", "set_led", "clear_leds", "play_spell", "send_macro")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Magic Caster Wand BLE device from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = entry.unique_id
    device_type = entry.data.get("device_type", "mcw")
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
    if device_type == "mcb":
        device = McbDevice(address)
    else:
        device = McwDevice(address, tflite_url=tflite_url, spell_timeout=spell_timeout)

    identifier = address.replace(":", "")[-8:]

    # Create coordinators with unique names for debugging
    coordinator: DataUpdateCoordinator[BLEData] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_main_{identifier}",
        update_method=partial(_async_update_method, hass, entry, device),
        update_interval=timedelta(seconds=float(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))),
    )

    if device_type == "mcw":
        spell_coordinator: DataUpdateCoordinator[str] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_spell_{identifier}",
        )

        buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_buttons_{identifier}",
        )

        calibration_coordinator: DataUpdateCoordinator[dict[str, bool]] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_calibration_{identifier}",
        )

        imu_coordinator: DataUpdateCoordinator[list[dict[str, float]]] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_imu_{identifier}",
        )

    elif device_type == "mcb":
        lid_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_lid_{identifier}",
        )

        usb_plugged_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_usb_plugged_{identifier}",
        )

        wand_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_wand_present_{identifier}",
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

    # Register coordinators with device for BLE callbacks
    if device_type == "mcw":
        device.register_coordinator(
            spell_coordinator,
            battery_coordinator,
            buttons_coordinator,
            calibration_coordinator,
            imu_coordinator,
            connection_coordinator,
        )
    elif device_type == "mcb":
        device.register_coordinator(
            cn_battery=battery_coordinator,
            cn_lid=lid_coordinator,
            cn_charge=usb_plugged_coordinator,
            cn_wand=wand_coordinator,
            cn_connection=connection_coordinator,
        )

    # Store data for platforms
    if device_type == "mcw":
        hass.data[DOMAIN][entry.entry_id] = {
            "address": address,
            "device": device,
            "type": device_type,
            "coordinator": coordinator,
            "spell_coordinator": spell_coordinator,
            "battery_coordinator": battery_coordinator,
            "buttons_coordinator": buttons_coordinator,
            "calibration_coordinator": calibration_coordinator,
            "imu_coordinator": imu_coordinator,
            "connection_coordinator": connection_coordinator,
        }
    elif device_type == "mcb":
        hass.data[DOMAIN][entry.entry_id] = {
            "address": address,
            "device": device,
            "type": device_type,
            "coordinator": coordinator,
            "battery_coordinator": battery_coordinator,
            "lid_coordinator": lid_coordinator,
            "usb_plugged_coordinator": usb_plugged_coordinator,
            "wand_coordinator": wand_coordinator,
            "connection_coordinator": connection_coordinator,
        }

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

    # Register services
    async def handle_vibrate(call: ServiceCall) -> None:
        """Handle execution of vibrate service."""
        duration = call.data.get("duration", 500)
        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice | McbDevice = hass.data[DOMAIN][entry_id]["device"]
                await device.buzz(duration)

    async def handle_set_led(call: ServiceCall) -> None:
        """Handle execution of set_led service."""
        # Accepts the selector's uppercase names, but also lowercase or an index,
        # since script and automation calls bypass selector validation.
        group = resolve_led_group(call.data.get("group", "TIP"))
        rgb = call.data.get("rgb_color", (255, 255, 255))
        duration = call.data.get("duration", 0)
        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice | McbDevice = hass.data[DOMAIN][entry_id]["device"]
                await device.set_led(group, rgb[0], rgb[1], rgb[2], duration)

    async def handle_send_macro(call: ServiceCall) -> None:
        """Handle execution of send_macro service."""
        commands = call.data.get("commands", [])
        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice | McbDevice = hass.data[DOMAIN][entry_id]["device"]
                await device.send_macro_parse(commands)

    async def handle_clear_leds(call: ServiceCall) -> None:
        """Handle execution of clear_leds service."""
        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice | McbDevice = hass.data[DOMAIN][entry_id]["device"]
                await device.clear_leds()

    async def handle_play_spell(call: ServiceCall) -> None:
        """Handle execution of play_spell service."""
        spell_name = call.data.get("spell")
        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry_id = await get_entry_id_from_device(hass, device_id)
            if entry_id and entry_id in hass.data[DOMAIN]:
                device: McwDevice | McbDevice = hass.data[DOMAIN][entry_id]["device"]
                # Use helper for more robust spell matching
                from .mcw_ble import get_spell_macro

                macro = get_spell_macro(spell_name)
                if macro:
                    await device.send_macro(macro)

    handlers = {
        "vibrate": handle_vibrate,
        "set_led": handle_set_led,
        "clear_leds": handle_clear_leds,
        "play_spell": handle_play_spell,
        "send_macro": handle_send_macro,
    }
    for name in SERVICES:
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, handlers[name])

    return True


async def _async_update_method(hass: HomeAssistant, entry: ConfigEntry, mcw: McwDevice) -> BLEData:
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    mcw: McwDevice | McbDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    await mcw.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        # The services are registered once for the whole integration, so they
        # are only removed once the last device is gone.
        if not hass.data[DOMAIN]:
            for name in SERVICES:
                hass.services.async_remove(DOMAIN, name)

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


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
