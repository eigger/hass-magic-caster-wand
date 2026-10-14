"""Bluetooth advertisement parser for Magic Caster Box devices."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from ..ble_common.discovery import BLEDeviceData


class McbBluetoothDeviceData(BLEDeviceData):
    """Bluetooth device data for Magic Caster Box."""

    SERVICE_UUID = "57420001-587e-48a0-974c-54686f72c577"
    DEVICE_NAME_PREFIX = "MCB-"
    device_type = "mcb"

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the advertisement belongs to a box."""
        return super().supported(data)
