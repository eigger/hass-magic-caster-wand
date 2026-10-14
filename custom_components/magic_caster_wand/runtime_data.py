"""Typed runtime data owned by a Magic Caster Wand config entry."""

from dataclasses import dataclass
from typing import Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .mcw_ble import BLEData, McbDevice, McwDevice


@dataclass
class MagicCasterWandRuntimeData:
    """Objects created while a config entry is loaded."""

    address: str
    device_type: Literal["mcw", "mcb"]
    device: McwDevice | McbDevice
    coordinator: DataUpdateCoordinator[BLEData]
    battery_coordinator: DataUpdateCoordinator[float]
    connection_coordinator: DataUpdateCoordinator[bool]
    spell_coordinator: DataUpdateCoordinator[str] | None = None
    buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] | None = None
    calibration_coordinator: DataUpdateCoordinator[dict[str, str]] | None = None
    imu_coordinator: DataUpdateCoordinator[list[dict[str, float]]] | None = None
    lid_coordinator: DataUpdateCoordinator[bool] | None = None
    usb_plugged_coordinator: DataUpdateCoordinator[bool] | None = None
    wand_coordinator: DataUpdateCoordinator[bool] | None = None


MagicCasterWandConfigEntry = ConfigEntry[MagicCasterWandRuntimeData]
