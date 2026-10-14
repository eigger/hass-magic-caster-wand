"""Shared Bluetooth advertisement parser behavior."""

from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak


class BLEDeviceData(BluetoothData):
    """Base parser for a supported Magic Caster BLE advertisement."""

    SERVICE_UUID: str
    DEVICE_NAME_PREFIX: str
    device_type: str

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        self.pending = True

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is a supported Magic Caster Wand."""
        """Check whether the advertisement name matches this device type."""
        if not data.name or not data.name.startswith(self.DEVICE_NAME_PREFIX):
            return False
        return True
