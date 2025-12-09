"""The Mcw Bluetooth integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import McwPassiveBluetoothProcessorCoordinator

type McwConfigEntry = ConfigEntry[McwPassiveBluetoothProcessorCoordinator]
