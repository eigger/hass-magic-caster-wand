"""Tests for integration-wide service registration and dispatch."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.magic_caster_wand import services


class FakeServiceRegistry:
    def __init__(self):
        self.handlers = {}
        self.removed = []

    def has_service(self, domain, name):
        return (domain, name) in self.handlers

    def async_register(self, domain, name, handler):
        self.handlers[(domain, name)] = handler

    def async_remove(self, domain, name):
        self.removed.append((domain, name))


def test_services_register_once_for_the_integration():
    hass = SimpleNamespace(services=FakeServiceRegistry())

    async def scenario():
        await services.async_setup_services(hass)
        await services.async_setup_services(hass)

    asyncio.run(scenario())

    assert {name for _, name in hass.services.handlers} == set(services.SERVICES)


def test_services_are_removed_only_after_the_last_entry_unloads():
    remaining = SimpleNamespace(entry_id="second", runtime_data=object())
    hass = SimpleNamespace(
        services=FakeServiceRegistry(),
        config_entries=SimpleNamespace(async_entries=lambda _domain: [remaining]),
    )
    unloading = SimpleNamespace(entry_id="first")

    async def scenario():
        await services.async_unload_services(hass, unloading)
        hass.config_entries.async_entries = lambda _domain: []
        await services.async_unload_services(hass, remaining)

    asyncio.run(scenario())

    assert hass.services.removed == [(services.DOMAIN, name) for name in services.SERVICES]


def test_set_led_service_dispatches_to_the_config_entry_device(monkeypatch):
    device = SimpleNamespace(set_led=AsyncMock())
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace(device=device))
    device_entry = SimpleNamespace(config_entries={entry.entry_id})
    registry = SimpleNamespace(async_get=lambda _device_id: device_entry)
    monkeypatch.setattr(services.dr, "async_get", lambda _hass: registry)
    hass = SimpleNamespace(
        services=FakeServiceRegistry(),
        config_entries=SimpleNamespace(async_get_entry=lambda _entry_id: entry),
    )

    async def scenario():
        await services.async_setup_services(hass)
        handler = hass.services.handlers[(services.DOMAIN, "set_led")]
        await handler(SimpleNamespace(data={"device_id": "device-1", "group": "TIP", "rgb_color": [1, 2, 3]}))

    asyncio.run(scenario())

    device.set_led.assert_awaited_once()
    assert device.set_led.await_args.args[1:] == (1, 2, 3, 0)


@pytest.mark.parametrize(
    ("service_name", "data", "method_name", "expected_args"),
    [
        ("vibrate", {"device_id": "device-1", "duration": 250}, "buzz", (250,)),
        ("clear_leds", {"device_id": "device-1"}, "clear_leds", ()),
        ("play_spell", {"device_id": "device-1", "spell": "Lumos"}, "send_macro", ("macro",)),
        (
            "send_macro",
            {"device_id": "device-1", "commands": [{"clear": None}]},
            "send_macro_parse",
            ([{"clear": None}],),
        ),
    ],
)
def test_service_handlers_dispatch_to_the_selected_device(monkeypatch, service_name, data, method_name, expected_args):
    method = AsyncMock()
    device = SimpleNamespace(**{method_name: method})
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace(device=device))
    device_entry = SimpleNamespace(config_entries={entry.entry_id})
    registry = SimpleNamespace(async_get=lambda _device_id: device_entry)
    monkeypatch.setattr(services.dr, "async_get", lambda _hass: registry)
    monkeypatch.setattr(services, "get_spell_macro", lambda _name: "macro")
    hass = SimpleNamespace(
        services=FakeServiceRegistry(),
        config_entries=SimpleNamespace(async_get_entry=lambda _entry_id: entry),
    )

    async def scenario():
        await services.async_setup_services(hass)
        handler = hass.services.handlers[(services.DOMAIN, service_name)]
        await handler(SimpleNamespace(data=data))

    asyncio.run(scenario())

    method.assert_awaited_once_with(*expected_args)
