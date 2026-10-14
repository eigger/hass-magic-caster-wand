"""Bluetooth support for Magic Caster Box devices."""

from .discovery import McbBluetoothDeviceData
from .mcb import LIDSTATE
from .mcb_device import McbDevice

__all__ = ["LIDSTATE", "McbBluetoothDeviceData", "McbDevice"]
