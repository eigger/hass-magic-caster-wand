"""Integration actions through real HA services and device registry."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magic_caster_wand import services


async def test_services_register_once_for_the_integration(hass):
    await services.async_setup_services(hass)
    first = hass.services.async_services()[services.DOMAIN]
    await services.async_setup_services(hass)
    assert hass.services.async_services()[services.DOMAIN] == first
    assert set(first) == set(services.SERVICES)


async def test_services_are_removed_only_after_the_last_entry_unloads(hass, entry):
    remaining = MockConfigEntry(
        domain=services.DOMAIN, unique_id="AA:BB:CC:DD:EE:01", data={}, state=ConfigEntryState.LOADED
    )
    remaining.add_to_hass(hass)
    remaining.runtime_data = object()
    await services.async_setup_services(hass)
    await services.async_unload_services(hass, entry)
    assert all(hass.services.has_service(services.DOMAIN, name) for name in services.SERVICES)
    await services.async_unload_services(hass, remaining)
    assert all(not hass.services.has_service(services.DOMAIN, name) for name in services.SERVICES)


async def test_set_led_service_dispatches_to_the_config_entry_device(hass, entry, bluetooth_transport):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device_id = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
    with patch.object(entry.runtime_data.device, "set_led", new_callable=AsyncMock) as set_led:
        await hass.services.async_call(
            services.DOMAIN, "set_led", {"device_id": device_id, "group": "TIP", "rgb_color": [1, 2, 3]}, blocking=True
        )
        set_led.assert_awaited_once()
        assert set_led.await_args.args[1:] == (1, 2, 3, 0)
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("service_name", "data", "method_name", "expected_args"),
    [
        ("vibrate", {"duration": 250}, "buzz", (250,)),
        ("clear_leds", {}, "clear_leds", ()),
        ("play_spell", {"spell": "Lumos"}, "send_macro", ("macro",)),
        (
            "send_macro",
            {"commands": [{"clear": None}]},
            "send_macro_parse",
            ([{"clear": None}],),
        ),
    ],
)
async def test_service_handlers_dispatch_to_the_selected_device(
    hass, entry, bluetooth_transport, service_name, data, method_name, expected_args
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device_id = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
    with (
        patch.object(entry.runtime_data.device, method_name, new_callable=AsyncMock) as method,
        patch.object(services, "get_spell_macro", return_value="macro"),
    ):
        await hass.services.async_call(services.DOMAIN, service_name, {**data, "device_id": device_id}, blocking=True)
        method.assert_awaited_once_with(*expected_args)
    assert await hass.config_entries.async_unload(entry.entry_id)
