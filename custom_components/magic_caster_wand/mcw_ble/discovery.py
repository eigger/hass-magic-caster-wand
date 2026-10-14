"""Bluetooth advertisement parser for Magic Caster Wand devices."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from ..common_ble.discovery import BLEDeviceData


class McwBluetoothDeviceData(BLEDeviceData):
    """Bluetooth device data for Magic Caster Wand."""

    SERVICE_UUID = "57420001-587e-48a0-974c-544d6163c577"
    DEVICE_NAME_PREFIX = "MCW-"
    device_type = "mcw"

    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        """Check if the advertisement belongs to a wand."""
        return super().supported(data)
