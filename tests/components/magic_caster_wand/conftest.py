"""Fixtures for real Home Assistant integration loading."""

# <!-- hass-standards:domain-fixtures:start -->
# Use pytest_homeassistant_custom_component.common.MockConfigEntry for
# mock_config_entry when the integration uses config entries.
# Define mock_client only when an external communication client is present.
# Mock external communication boundaries, never Home Assistant core modules.
# Keep integration-specific fixtures below this managed block.
# <!-- hass-standards:domain-fixtures:end -->

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magic_caster_wand.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def mock_config_entry(hass):
    """An existing entry, including the pre-box schema without device_type."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, title="Test Wand", data={})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def entry(mock_config_entry):
    """Preserve the existing regression suite's fixture name."""
    return mock_config_entry


@pytest.fixture
def mock_client(mock_bluetooth):
    """Mock only Bluetooth adapter access and device network operations."""
    with (
        patch("custom_components.magic_caster_wand.close_stale_connections_by_address", new_callable=AsyncMock),
        patch("custom_components.magic_caster_wand.bluetooth.async_ble_device_from_address", return_value=None),
        patch(
            "custom_components.magic_caster_wand.mcw_ble.mcw_device.McwDevice.disconnect", new_callable=AsyncMock
        ) as disconnect,
    ):
        yield disconnect


@pytest.fixture
def bluetooth_transport(mock_client):
    """Preserve the existing external Bluetooth fixture name."""
    return mock_client


@pytest.fixture
async def loaded_wand(hass, entry, bluetooth_transport):
    """Load real HA platforms with only the Bluetooth boundary mocked."""
    from homeassistant.helpers import entity_registry as er

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    def entity_id(platform, suffix):
        return next(
            entity.entity_id
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
            if entity.domain == platform and entity.unique_id.endswith("_" + suffix)
        )

    yield entry.runtime_data, entity_id
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
