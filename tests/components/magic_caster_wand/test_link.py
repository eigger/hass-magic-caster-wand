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


def _entry(hass, address, device_type, wand_address=None, state=None, with_runtime_data=True):
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=link.DOMAIN,
        unique_id=address,
        data={"device_type": device_type},
        state=state or link.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    if with_runtime_data:
        entry.runtime_data = SimpleNamespace(device=SimpleNamespace(wand_address=wand_address))
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, connections={(dr.CONNECTION_BLUETOOTH, address)}
    )
    return entry, device


async def test_reconcile_links_wand_to_box(hass):
    _, box = _entry(hass, BOX, "mcb", WAND)
    _, wand = _entry(hass, WAND, "mcw")
    await link.async_reconcile_links(hass)
    registry = link.dr.async_get(hass)
    assert registry.async_get(wand.id).via_device_id == box.id
    await link.async_reconcile_links(hass)
    assert registry.async_get(wand.id).via_device_id == box.id


async def test_reconcile_counts_entries_still_setting_up(hass):
    in_progress = link.ConfigEntryState.SETUP_IN_PROGRESS
    _, box = _entry(hass, BOX, "mcb", WAND, state=in_progress)
    _, wand = _entry(hass, WAND, "mcw", state=in_progress)
    await link.async_reconcile_links(hass)
    assert link.dr.async_get(hass).async_get(wand.id).via_device_id == box.id


async def test_reconcile_skips_entry_without_runtime_data(hass):
    _entry(hass, BOX, "mcb", WAND, state=link.ConfigEntryState.SETUP_IN_PROGRESS, with_runtime_data=False)
    _, wand = _entry(hass, WAND, "mcw")
    await link.async_reconcile_links(hass)
    assert link.dr.async_get(hass).async_get(wand.id).via_device_id is None


async def test_reconcile_ignores_unloaded_entries(hass):
    _entry(hass, BOX, "mcb", WAND, state=link.ConfigEntryState.NOT_LOADED)
    _, wand = _entry(hass, WAND, "mcw")
    await link.async_reconcile_links(hass)
    assert link.dr.async_get(hass).async_get(wand.id).via_device_id is None


async def test_unpaired_box_does_not_unlink(hass):
    _, box = _entry(hass, BOX, "mcb", "00:00:00:00:00:00")
    _, wand = _entry(hass, WAND, "mcw")
    registry = link.dr.async_get(hass)
    registry.async_update_device(wand.id, via_device_id=box.id)
    await link.async_reconcile_links(hass)
    assert registry.async_get(wand.id).via_device_id == box.id


async def test_reconcile_without_wand_entry_does_nothing(hass):
    _, box = _entry(hass, BOX, "mcb", WAND)
    await link.async_reconcile_links(hass)
    assert link.dr.async_get(hass).async_get(box.id).via_device_id is None


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


async def test_reconcile_unlinks_wand_when_box_reports_another(hass):
    _, box = _entry(hass, BOX, "mcb", "AA:AA:AA:AA:AA:AA")
    _, wand = _entry(hass, WAND, "mcw")
    registry = link.dr.async_get(hass)
    registry.async_update_device(wand.id, via_device_id=box.id)
    await link.async_reconcile_links(hass)
    assert registry.async_get(wand.id).via_device_id is None
