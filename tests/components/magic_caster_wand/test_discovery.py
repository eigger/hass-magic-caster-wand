"""Tests for how discovered BLE advertisements are matched to a device type."""

from types import SimpleNamespace

import pytest

from custom_components.magic_caster_wand.mcw_ble.parser import (
    McbBluetoothDeviceData,
    McwBluetoothDeviceData,
)

# Mirrors config_flow.DEVICE_TYPES; the first match wins.
DEVICE_TYPES = [McwBluetoothDeviceData, McbBluetoothDeviceData]


def advertisement(name):
    return SimpleNamespace(name=name, service_uuids=[], address="AA:BB:CC:DD:EE:FF")


def detect(name):
    """Return the device_type the config flow would pick, or None."""
    for device_cls in DEVICE_TYPES:
        device = device_cls()
        if device.supported(advertisement(name)):
            return device.device_type
    return None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MCW-1234", "mcw"),
        ("MCB-1234", "mcb"),
        ("MCW-", "mcw"),
        ("MCB-", "mcb"),
    ],
)
def test_known_prefixes_resolve_to_a_device_type(name, expected):
    assert detect(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        "MCW",  # prefix without the separator
        "MCB",
        "mcw-1234",  # matching is case sensitive
        "mcb-1234",
        "XMCW-1234",  # prefix must be at the start
        "Some Other Device",
    ],
)
def test_unrelated_advertisements_are_not_supported(name):
    assert detect(name) is None


def test_device_types_are_mutually_exclusive():
    """A wand must never be claimed by the box handler, or vice versa."""
    assert McwBluetoothDeviceData().supported(advertisement("MCB-1234")) is False
    assert McbBluetoothDeviceData().supported(advertisement("MCW-1234")) is False


def test_device_type_markers_are_distinct():
    assert McwBluetoothDeviceData.device_type == "mcw"
    assert McbBluetoothDeviceData.device_type == "mcb"


def test_wand_and_box_use_different_service_uuids():
    assert McwBluetoothDeviceData.SERVICE_UUID != McbBluetoothDeviceData.SERVICE_UUID
