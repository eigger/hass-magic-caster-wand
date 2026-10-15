"""Linking a box to the wand it reports as paired."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.magic_caster_wand import link
from custom_components.magic_caster_wand.link import plan_links
from custom_components.magic_caster_wand.mcb_ble import McbDevice

BOX = "FA:59:68:25:7B:68"
WAND = "E0:F8:53:63:F8:EA"


def test_wand_is_parented_to_the_box_that_reports_it():
    assert plan_links({"box": WAND}, {WAND: ("wand", None)}) == {"wand": "box"}


def test_already_linked_wand_needs_no_change():
    assert plan_links({"box": WAND}, {WAND: ("wand", "box")}) == {}


def test_unknown_box_answer_never_unlinks():
    assert plan_links({"box": None}, {WAND: ("wand", "box")}) == {}


def test_box_reporting_another_wand_unlinks_the_old_one():
    assert plan_links({"box": "AA:AA:AA:AA:AA:AA"}, {WAND: ("wand", "box")}) == {"wand": None}


def test_foreign_parent_is_left_alone():
    assert plan_links({"box": "AA:AA:AA:AA:AA:AA"}, {WAND: ("wand", "hub")}) == {}


def test_wand_without_box_is_untouched():
    assert plan_links({}, {WAND: ("wand", None)}) == {}


class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices  # address -> SimpleNamespace(id, via_device_id)
        self.updates = []

    def async_get_device(self, connections):
        ((_, address),) = connections
        return self.devices.get(address)

    def async_get(self, device_id):
        return next(d for d in self.devices.values() if d.id == device_id)

    def async_update_device(self, device_id, via_device_id=None):
        self.updates.append((device_id, via_device_id))
        self.async_get(device_id).via_device_id = via_device_id


def _entry(address, device_type, wand_address=None):
    return SimpleNamespace(
        state=link.ConfigEntryState.LOADED,
        unique_id=address,
        data={"device_type": device_type},
        runtime_data=SimpleNamespace(device=SimpleNamespace(wand_address=wand_address)),
    )


def _setup(monkeypatch, entries, registry):
    link.dr.async_get = MagicMock(return_value=registry)
    link.dr.CONNECTION_BLUETOOTH = "bluetooth"
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain: entries))
    return hass


def test_reconcile_links_wand_to_box(monkeypatch):
    registry = FakeRegistry(
        {BOX: SimpleNamespace(id="box", via_device_id=None), WAND: SimpleNamespace(id="wand", via_device_id=None)}
    )
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", WAND), _entry(WAND, "mcw")], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", "box")]
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", "box")]


def test_reconcile_without_wand_entry_does_nothing(monkeypatch):
    registry = FakeRegistry({BOX: SimpleNamespace(id="box", via_device_id=None)})
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", WAND)], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == []


class _Mcb:
    def __init__(self, result):
        self.result = result

    async def get_wand_address(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _box(result):
    device = McbDevice(BOX)
    device._mcb = _Mcb(result)
    device.on_wand_address_changed = MagicMock()
    return device


def test_box_reports_wand_address_change():
    device = _box(WAND)
    asyncio.run(device._refresh_wand_address())
    assert device.wand_address == WAND
    device.on_wand_address_changed.assert_called_once()
    asyncio.run(device._refresh_wand_address())
    device.on_wand_address_changed.assert_called_once()


@pytest.mark.parametrize("result", ["", TimeoutError("no answer")])
def test_unanswered_wand_address_keeps_known_value(result):
    device = _box(result)
    device.wand_address = WAND
    asyncio.run(device._refresh_wand_address())
    assert device.wand_address == WAND
    device.on_wand_address_changed.assert_not_called()
