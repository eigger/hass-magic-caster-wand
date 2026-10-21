"""Calibration uses real HA button services and the external device boundary."""

from unittest.mock import AsyncMock, patch


async def test_calibration_service_sends_device_command(hass, loaded_wand):
    runtime, entity_id = loaded_wand
    runtime.connection_coordinator.async_set_updated_data(True)
    await hass.async_block_till_done()
    with patch.object(runtime.device, "send_button_calibration", new_callable=AsyncMock) as send:
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id("button", "calibration_button")}, blocking=True
        )
        send.assert_awaited_once()
    assert runtime.calibration_coordinator.data["calibration_button"] == "Pending"
