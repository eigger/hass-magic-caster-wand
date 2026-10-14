"""Bluetooth advertisement parsers for wand and box devices."""

from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfoBleak


class McwBluetoothDeviceData(BluetoothData):
    """Bluetooth device data for Magic Caster Wand."""

    # Magic Caster Wand Service UUID (from mcw.py)
    SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
    # Device name prefix
    DEVICE_NAME_PREFIX = "MCW-"
    device_type = "mcw"

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        self.pending = True

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is a supported Magic Caster Wand."""
        # Check device name starts with "MCW-"
        if not data.name or not data.name.startswith(self.DEVICE_NAME_PREFIX):
            return False

        # Check for Magic Caster Wand Service UUID
        # service_uuids_lower = [uuid.lower() for uuid in data.service_uuids]
        # if self.SERVICE_UUID.lower() not in service_uuids_lower:
        #     return False

        return True


class McbBluetoothDeviceData(BluetoothData):
    """Bluetooth device data for Magic Caster Box."""

    # Magic Caster Box Service UUID (from mcb.py)
    SERVICE_UUID = "57420001-587e-48a0-974c-54686f72c577"
    # Device name prefix
    DEVICE_NAME_PREFIX = "MCB-"
    device_type = "mcb"

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        self.pending = True

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is a supported Magic Caster Box."""
        # Check device name starts with "MCB-"
        if not data.name or not data.name.startswith(self.DEVICE_NAME_PREFIX):
            return False

        # Check for Magic Caster Box Service UUID
        # service_uuids_lower = [uuid.lower() for uuid in data.service_uuids]
        # if self.SERVICE_UUID.lower() not in service_uuids_lower:
        #     return False

        return True
