"""Typed runtime data owned by a Magic Caster Wand config entry."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common_ble import BLEData
from .mcb_ble import McbDevice
from .mcw_ble import McwDevice


@dataclass
class MagicCasterWandRuntimeData:
    """Runtime objects shared by every supported device."""

    address: str
    device: McwDevice | McbDevice
    coordinator: DataUpdateCoordinator[BLEData]
    battery_coordinator: DataUpdateCoordinator[float]
    connection_coordinator: DataUpdateCoordinator[bool]


@dataclass
class McwRuntimeData(MagicCasterWandRuntimeData):
    """Runtime objects used by a wand and its entities."""

    device: McwDevice
    spell_coordinator: DataUpdateCoordinator[str]
    buttons_coordinator: DataUpdateCoordinator[dict[str, bool]]
    calibration_coordinator: DataUpdateCoordinator[dict[str, str]]
    imu_coordinator: DataUpdateCoordinator[list[dict[str, float]]]


@dataclass
class McbRuntimeData(MagicCasterWandRuntimeData):
    """Runtime objects used by a box and its entities."""

    device: McbDevice
    lid_coordinator: DataUpdateCoordinator[bool]
    usb_plugged_coordinator: DataUpdateCoordinator[bool]
    wand_coordinator: DataUpdateCoordinator[bool]


MagicCasterWandConfigEntry = ConfigEntry[MagicCasterWandRuntimeData]
