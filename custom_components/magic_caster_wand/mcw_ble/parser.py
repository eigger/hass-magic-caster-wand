"""Compatibility exports for BLE device models and discovery parsers."""

from .common import HOLD_DURATION_MS, BLEData, build_macro, build_set_led_macro, resolve_led_group
from .discovery import McbBluetoothDeviceData, McwBluetoothDeviceData
from .macros import LedGroup, Macro
from .mcb_device import McbDevice
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
