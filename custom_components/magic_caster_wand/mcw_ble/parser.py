"""Compatibility exports for BLE device models and discovery parsers."""

from ..ble_common.common import HOLD_DURATION_MS, BLEData, build_macro, build_set_led_macro, resolve_led_group
from ..ble_common.macros import LedGroup, Macro
from ..mcb_ble import McbBluetoothDeviceData, McbDevice
from .discovery import McwBluetoothDeviceData
from .mcw_device import McwDevice

__all__ = [
    "BLEData",
    "HOLD_DURATION_MS",
    "LedGroup",
    "Macro",
    "McbBluetoothDeviceData",
    "McbDevice",
    "McwBluetoothDeviceData",
    "McwDevice",
    "build_macro",
    "build_set_led_macro",
    "resolve_led_group",
]
