"""Config flow tests through the real Home Assistant flow manager."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_REAUTH, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.magic_caster_wand.const import DOMAIN


def advertisement(name="MCW-Test"):
    """Provide a BLE advertisement at the external communication boundary."""
    import inspect

    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

    extra = {"rssi": -60} if "rssi" in inspect.signature(BLEDevice).parameters else {}
    device = BLEDevice("AA:BB:CC:DD:EE:FF", name, {}, **extra)
    return BluetoothServiceInfoBleak.from_scan(
        "test",
        device,
        AdvertisementData(
            local_name=name,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            tx_power=None,
            rssi=-60,
            platform_data=(),
        ),
        0,
        True,
    )


async def test_user_no_discovered_devices(hass, bluetooth_transport):
    with patch("custom_components.magic_caster_wand.config_flow.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_discovery_confirm_and_duplicate(hass, bluetooth_transport):
    with patch("homeassistant.components.onboarding.async_is_onboarded", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=advertisement()
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"device_type": "mcw"}
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"
    assert await hass.config_entries.async_unload(entry.entry_id)
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=advertisement()
    )
    assert duplicate["reason"] == "already_configured"


async def test_unsupported_discovery(hass, bluetooth_transport):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=advertisement("Other device")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_reauth_accepts_persisted_entry_data(hass, entry, bluetooth_transport):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_box_user_selection(hass, bluetooth_transport):
    with patch(
        "custom_components.magic_caster_wand.config_flow.async_discovered_service_info",
        return_value=[advertisement("MCB-Test")],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"address": "AA:BB:CC:DD:EE:FF"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"device_type": "mcb"}
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(result["result"].entry_id)


async def test_options_flow_updates_and_reloads_entry(hass, entry, bluetooth_transport):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    previous = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"tflite_url": "http://192.0.2.10:5000", "spell_timeout": 2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["spell_timeout"] == 2
    assert entry.runtime_data is not previous
    assert await hass.config_entries.async_unload(entry.entry_id)
