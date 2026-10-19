"""Services provided by the Magic Caster Wand integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .common_ble import resolve_led_group
from .const import DOMAIN
from .mcb_ble import McbDevice
from .mcw_ble import McwDevice, get_spell_macro

if TYPE_CHECKING:
    from .runtime_data import MagicCasterWandConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICES = ("vibrate", "set_led", "clear_leds", "play_spell", "send_macro")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-wide services once, when the first entry loads."""

    async def handle_vibrate(call: ServiceCall) -> None:
        duration = call.data.get("duration", 500)
        for device_id in _device_ids(hass, call):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if device := _get_device_by_entry_id(hass, entry_id):
                await device.buzz(duration)

    async def handle_set_led(call: ServiceCall) -> None:
        # Scripts and automations bypass the selector's input validation.
        group = resolve_led_group(call.data.get("group", "TIP"))
        rgb = call.data.get("rgb_color", (255, 255, 255))
        duration = call.data.get("duration", 0)
        for device_id in _device_ids(hass, call):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if device := _get_device_by_entry_id(hass, entry_id):
                await device.set_led(group, rgb[0], rgb[1], rgb[2], duration)

    async def handle_send_macro(call: ServiceCall) -> None:
        commands = call.data.get("commands", [])
        for device_id in _device_ids(hass, call):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if device := _get_device_by_entry_id(hass, entry_id):
                await device.send_macro_parse(commands)

    async def handle_clear_leds(call: ServiceCall) -> None:
        for device_id in _device_ids(hass, call):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if device := _get_device_by_entry_id(hass, entry_id):
                await device.clear_leds()

    async def handle_play_spell(call: ServiceCall) -> None:
        spell_name = call.data.get("spell")
        for device_id in _device_ids(hass, call):
            entry_id = await get_entry_id_from_device(hass, device_id)
            if device := _get_device_by_entry_id(hass, entry_id):
                if macro := get_spell_macro(spell_name):
                    await device.send_macro(macro)
                else:
                    _LOGGER.debug("Unknown spell requested by service: %s", spell_name)

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


async def async_unload_services(hass: HomeAssistant, entry: MagicCasterWandConfigEntry) -> None:
    """Remove integration-wide services after the final loaded entry unloads."""
    other_loaded_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry.entry_id
        and getattr(config_entry, "runtime_data", None) is not None
    ]
    if not other_loaded_entries:
        for name in SERVICES:
            hass.services.async_remove(DOMAIN, name)


def _device_ids(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Resolve entity or device service targets to unique device registry IDs."""
    device_ids = call.data.get("device_id", [])
    entity_ids = call.data.get("entity_id", [])
    device_ids = [device_ids] if isinstance(device_ids, str) else list(device_ids)
    entity_ids = [entity_ids] if isinstance(entity_ids, str) else list(entity_ids)

    if entity_ids:
        entity_reg = er.async_get(hass)
        for entity_id in entity_ids:
            if entity := entity_reg.async_get(entity_id):
                if entity.device_id:
                    device_ids.append(entity.device_id)

    return list(dict.fromkeys(device_ids))


def _get_device_by_entry_id(hass: HomeAssistant, entry_id: str | None) -> McwDevice | McbDevice | None:
    """Get a loaded device from a config entry ID."""
    if entry_id is None:
        return None
    config_entry = hass.config_entries.async_get_entry(entry_id)
    runtime_data = getattr(config_entry, "runtime_data", None)
    return runtime_data.device if runtime_data else None


async def get_entry_id_from_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Resolve a device registry ID to its owning config entry ID."""
    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get(device_id)
    if not device_entry:
        raise ValueError(f"Unknown device_id: {device_id}")
    if not device_entry.config_entries:
        raise ValueError(f"No config entries for device {device_id}")

    _LOGGER.debug("%s to %s", device_id, device_entry.config_entries)
    try:
        return next(iter(device_entry.config_entries))
    except StopIteration:
        _LOGGER.error("%s None", device_id)
        return None
