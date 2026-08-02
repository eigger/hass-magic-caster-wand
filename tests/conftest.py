"""Test bootstrap.

The integration modules import Home Assistant and BLE libraries at module level.
Those are not installed for a bare unit-test run, so stub them out in
``sys.modules`` before any test imports the component. Only the pure protocol
and macro-building logic is exercised, so mocks are enough.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MockBase:
    """Stand-in for a base class that also supports subscripting (``Base[T]``)."""

    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls


# ── Home Assistant ────────────────────────────────────────────────────────────

ha_exceptions = MagicMock()


class MockHomeAssistantError(Exception):
    """Mock HomeAssistantError."""


ha_exceptions.HomeAssistantError = MockHomeAssistantError
sys.modules["homeassistant.exceptions"] = ha_exceptions

sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.bluetooth"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()

# ── External libraries ────────────────────────────────────────────────────────

bleak = MagicMock()
bleak.BleakError = type("BleakError", (Exception,), {})
sys.modules["bleak"] = bleak
sys.modules["bleak.backends.device"] = MagicMock()
sys.modules["bleak_retry_connector"] = MagicMock()

bt_sensor_state_data = MagicMock()
bt_sensor_state_data.BluetoothData = MockBase
sys.modules["bluetooth_sensor_state_data"] = bt_sensor_state_data

sys.modules["home_assistant_bluetooth"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
