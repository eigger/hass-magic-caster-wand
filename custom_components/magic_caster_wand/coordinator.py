"""The Mcw Bluetooth integration."""

from collections.abc import Callable, Coroutine
from logging import Logger
from typing import Any

from .mcw_ble import McwBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant

from .types import McwConfigEntry


class McwPassiveBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Define a Mcw Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        device_data: McwBluetoothDeviceData,
        discovered_event_classes: set[str],
        entry: McwConfigEntry,
        connectable: bool = True,
    ) -> None:
        """Initialize the Mcw Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method, connectable)
        self.discovered_event_classes = discovered_event_classes
        self.device_data = device_data
        self.entry = entry


class McwPassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a Mcw Bluetooth Passive Update Data Processor."""

    coordinator: McwPassiveBluetoothProcessorCoordinator
