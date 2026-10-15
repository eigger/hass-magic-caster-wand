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
        self.devices = devices  # address -> SimpleNamespace(id, entry_id, connections, via_device_id)
        self.updates = []

    def entries_for(self, entry_id):
        return [d for d in self.devices.values() if d.entry_id == entry_id]

    def async_get(self, device_id):
        return next(d for d in self.devices.values() if d.id == device_id)

    def async_update_device(self, device_id, via_device_id):
        self.updates.append((device_id, via_device_id))
        self.async_get(device_id).via_device_id = via_device_id


def _entry(address, device_type, wand_address=None, state=None, with_runtime_data=True):
    entry = SimpleNamespace(
        state=state or link.ConfigEntryState.LOADED,
        unique_id=address,
        entry_id=address,
        data={"device_type": device_type},
    )
    if with_runtime_data:
        entry.runtime_data = SimpleNamespace(device=SimpleNamespace(wand_address=wand_address))
    return entry


def _setup(monkeypatch, entries, registry):
    monkeypatch.setattr(link.dr, "async_get", MagicMock(return_value=registry))
    monkeypatch.setattr(link.dr, "CONNECTION_BLUETOOTH", "bluetooth")
    monkeypatch.setattr(link.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries_for(entry_id))
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain: entries))
    return hass


def test_reconcile_links_wand_to_box(monkeypatch):
    registry = _registry()
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", WAND), _entry(WAND, "mcw")], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", "box")]
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", "box")]


def _registry():
    return FakeRegistry(
        {
            BOX: SimpleNamespace(id="box", entry_id=BOX, connections={("bluetooth", BOX)}, via_device_id=None),
            WAND: SimpleNamespace(id="wand", entry_id=WAND, connections={("bluetooth", WAND)}, via_device_id=None),
        }
    )


def test_reconcile_counts_entries_still_setting_up(monkeypatch):
    """Reconcile runs inside setup, when HA still reports the entry as in progress."""
    registry = _registry()
    in_progress = link.ConfigEntryState.SETUP_IN_PROGRESS
    hass = _setup(
        monkeypatch,
        [_entry(BOX, "mcb", WAND, state=in_progress), _entry(WAND, "mcw", state=in_progress)],
        registry,
    )
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", "box")]


def test_reconcile_skips_entry_without_runtime_data(monkeypatch):
    registry = _registry()
    in_progress = link.ConfigEntryState.SETUP_IN_PROGRESS
    hass = _setup(
        monkeypatch,
        [_entry(BOX, "mcb", WAND, state=in_progress, with_runtime_data=False), _entry(WAND, "mcw")],
        registry,
    )
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == []


def test_reconcile_ignores_unloaded_entries(monkeypatch):
    registry = _registry()
    hass = _setup(
        monkeypatch,
        [_entry(BOX, "mcb", WAND, state=link.ConfigEntryState.NOT_LOADED), _entry(WAND, "mcw")],
        registry,
    )
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == []


def test_unpaired_box_does_not_unlink(monkeypatch):
    registry = _registry()
    registry.devices[WAND].via_device_id = "box"
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", "00:00:00:00:00:00"), _entry(WAND, "mcw")], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == []


def test_reconcile_without_wand_entry_does_nothing(monkeypatch):
    registry = FakeRegistry(
        {BOX: SimpleNamespace(id="box", entry_id=BOX, connections={("bluetooth", BOX)}, via_device_id=None)}
    )
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", WAND)], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == []


class _Mcb:
    def __init__(self, result):
        self.result = result

    async def get_wand_address(self, timeout=5.0):
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


def test_reconcile_unlinks_wand_when_box_reports_another(monkeypatch):
    registry = _registry()
    registry.devices[WAND].via_device_id = "box"
    hass = _setup(monkeypatch, [_entry(BOX, "mcb", "AA:AA:AA:AA:AA:AA"), _entry(WAND, "mcw")], registry)
    asyncio.run(link.async_reconcile_links(hass))
    assert registry.updates == [("wand", None)]
