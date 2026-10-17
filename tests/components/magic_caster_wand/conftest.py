"""Fixtures for real Home Assistant integration loading."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magic_caster_wand.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def entry(hass):
    """An existing entry, including the pre-box schema without device_type."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, title="Test Wand", data={})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def bluetooth_transport(mock_bluetooth):
    """Mock only Bluetooth adapter access and device network operations."""
    with (
        patch("custom_components.magic_caster_wand.close_stale_connections_by_address", new_callable=AsyncMock),
        patch("custom_components.magic_caster_wand.bluetooth.async_ble_device_from_address", return_value=None),
        patch(
            "custom_components.magic_caster_wand.mcw_ble.mcw_device.McwDevice.disconnect", new_callable=AsyncMock
        ) as disconnect,
    ):
        yield disconnect
