"""Exercise actual HA entry, platform, state and registry lifecycle."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.magic_caster_wand.const import DOMAIN
from custom_components.magic_caster_wand.runtime_data import McwRuntimeData


async def test_setup_unload_reload(hass, entry, bluetooth_transport):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, McwRuntimeData)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {entity.domain for entity in entities} == {
        "sensor",
        "switch",
        "text",
        "select",
        "binary_sensor",
        "button",
        "camera",
    }
    camera_id = next(entity.entity_id for entity in entities if entity.domain == "camera")
    assert hass.states.get(camera_id) is not None
    assert len(dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)) == 1
    runtime = entry.runtime_data
    runtime.connection_coordinator.async_set_updated_data(True)
    runtime.battery_coordinator.async_set_updated_data(72)
    await hass.async_block_till_done()
    battery_id = next(entity.entity_id for entity in entities if entity.unique_id.endswith("_battery"))
    assert hass.states.get(battery_id).state == "72"
    assert hass.services.has_service(DOMAIN, "vibrate")
    with patch.object(runtime.device, "buzz", new_callable=AsyncMock) as buzz:
        device_id = registry.async_get(battery_id).device_id
        await hass.services.async_call(DOMAIN, "vibrate", {"device_id": device_id, "duration": 250}, blocking=True)
        buzz.assert_awaited_once_with(250)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    bluetooth_transport.assert_awaited_once()
    assert not hass.services.has_service(DOMAIN, "vibrate")
    assert hass.states.get(camera_id).state == "unavailable"
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert {entity.unique_id for entity in er.async_entries_for_config_entry(registry, entry.entry_id)} == {
        entity.unique_id for entity in entities
    }
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("failure", [RuntimeError("platform load failed"), asyncio.CancelledError()])
async def test_failed_setup_closes_resources(hass, entry, bluetooth_transport, failure):
    with (
        patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=failure),
        patch(
            "custom_components.magic_caster_wand.mcw_ble.mcw_device.McwDevice.async_spell_tracker_close",
            new_callable=AsyncMock,
        ) as close_tracker,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        bluetooth_transport.assert_awaited_once()
        close_tracker.assert_awaited_once()


async def test_failed_unload_keeps_connection(hass, entry, bluetooth_transport):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    bluetooth_transport.assert_not_awaited()
    # HA marks rejected unloads FAILED_UNLOAD; clean the actual platforms for
    # this failure-injection test without resetting HA's entry state.
    from custom_components.magic_caster_wand import async_unload_entry

    assert await async_unload_entry(hass, entry)


async def test_last_unload_removes_services_after_two_entries(hass, entry, bluetooth_transport):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    second = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:01", title="Second wand", data={})
    second.add_to_hass(hass)
    # Loading the domain schedules all existing entries through HA itself.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert second.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "vibrate")
    assert await hass.config_entries.async_unload(second.entry_id)
    assert not hass.services.has_service(DOMAIN, "vibrate")


async def test_failure_after_platform_loading_removes_entities(hass, entry, bluetooth_transport):
    with patch("custom_components.magic_caster_wand.async_reconcile_links", side_effect=RuntimeError("link failed")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    bluetooth_transport.assert_awaited_once()
    assert not hass.services.has_service(DOMAIN, "vibrate")
    # HA restores registry placeholders on unload, but active entities are gone.
    for state in hass.states.async_all():
        if state.entity_id.startswith(("sensor.magic_caster_", "camera.magic_caster_")):
            assert state.attributes.get("restored") is True
