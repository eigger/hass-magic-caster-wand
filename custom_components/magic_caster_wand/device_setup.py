"""Factories for device-specific config-entry setup."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeAlias

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common_ble import BLEData
from .const import DOMAIN
from .mcb_ble import McbDevice
from .mcw_ble import McwDevice
from .runtime_data import McbRuntimeData, McwRuntimeData

Device: TypeAlias = McwDevice | McbDevice
DeviceFactory: TypeAlias = Callable[[str, str, int], Device]


def create_device(
    device_type: str,
    address: str,
    tflite_url: str,
    spell_timeout: int,
    hass: HomeAssistant,
) -> Device:
    """Create the selected device implementation from config-entry options."""
    factories: dict[str, DeviceFactory] = {
        "mcw": lambda addr, url, timeout: McwDevice(addr, tflite_url=url, spell_timeout=timeout, hass=hass),
        "mcb": lambda addr, _url, _timeout: McbDevice(addr, hass=hass),
    }
    return factories[device_type](address, tflite_url, spell_timeout)


def create_runtime_data(
    hass: HomeAssistant,
    logger: logging.Logger,
    address: str,
    identifier: str,
    device: Device,
    coordinator: DataUpdateCoordinator[BLEData],
    battery_coordinator: DataUpdateCoordinator[float],
    connection_coordinator: DataUpdateCoordinator[bool],
) -> McwRuntimeData | McbRuntimeData:
    """Create and register the device-specific coordinators and runtime type."""
    setup = {
        McwDevice: _create_mcw_runtime_data,
        McbDevice: _create_mcb_runtime_data,
    }[type(device)]
    return setup(
        hass,
        logger,
        address,
        identifier,
        device,
        coordinator,
        battery_coordinator,
        connection_coordinator,
    )


def _create_mcw_runtime_data(
    hass: HomeAssistant,
    logger: logging.Logger,
    address: str,
    identifier: str,
    device: McwDevice,
    coordinator: DataUpdateCoordinator[BLEData],
    battery_coordinator: DataUpdateCoordinator[float],
    connection_coordinator: DataUpdateCoordinator[bool],
) -> McwRuntimeData:
    """Create coordinators and runtime state for one wand."""
    spell_coordinator: DataUpdateCoordinator[str] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_spell_{identifier}",
    )
    buttons_coordinator: DataUpdateCoordinator[dict[str, bool]] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_buttons_{identifier}",
    )
    calibration_coordinator: DataUpdateCoordinator[dict[str, str]] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_calibration_{identifier}",
    )
    imu_coordinator: DataUpdateCoordinator[list[dict[str, float]]] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_imu_{identifier}",
    )

    device.register_coordinator(
        spell_coordinator,
        battery_coordinator,
        buttons_coordinator,
        calibration_coordinator,
        imu_coordinator,
        connection_coordinator,
    )
    return McwRuntimeData(
        address=address,
        device=device,
        coordinator=coordinator,
        battery_coordinator=battery_coordinator,
        connection_coordinator=connection_coordinator,
        diagnostics=device.diagnostics,
        spell_coordinator=spell_coordinator,
        buttons_coordinator=buttons_coordinator,
        calibration_coordinator=calibration_coordinator,
        imu_coordinator=imu_coordinator,
    )


def _create_mcb_runtime_data(
    hass: HomeAssistant,
    logger: logging.Logger,
    address: str,
    identifier: str,
    device: McbDevice,
    coordinator: DataUpdateCoordinator[BLEData],
    battery_coordinator: DataUpdateCoordinator[float],
    connection_coordinator: DataUpdateCoordinator[bool],
) -> McbRuntimeData:
    """Create coordinators and runtime state for one box."""
    lid_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_lid_{identifier}",
    )
    usb_plugged_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_usb_plugged_{identifier}",
    )
    wand_coordinator: DataUpdateCoordinator[bool] = DataUpdateCoordinator(
        hass,
        logger,
        name=f"{DOMAIN}_wand_present_{identifier}",
    )

    device.register_coordinator(
        cn_battery=battery_coordinator,
        cn_lid=lid_coordinator,
        cn_charge=usb_plugged_coordinator,
        cn_wand=wand_coordinator,
        cn_connection=connection_coordinator,
    )
    return McbRuntimeData(
        address=address,
        device=device,
        coordinator=coordinator,
        battery_coordinator=battery_coordinator,
        connection_coordinator=connection_coordinator,
        diagnostics=device.diagnostics,
        lid_coordinator=lid_coordinator,
        usb_plugged_coordinator=usb_plugged_coordinator,
        wand_coordinator=wand_coordinator,
    )
