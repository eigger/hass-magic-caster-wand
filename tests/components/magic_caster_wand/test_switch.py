"""Connection switch invokes only the external device disconnect boundary."""

from unittest.mock import AsyncMock, patch


async def test_connection_switch_turn_off(hass, loaded_wand):
    runtime, entity_id = loaded_wand
    runtime.connection_coordinator.async_set_updated_data(True)
    await hass.async_block_till_done()
    connect = entity_id("switch", "connect")
    assert hass.states.get(connect).state == "on"
    with patch.object(runtime.device, "disconnect", new_callable=AsyncMock) as disconnect:
        await hass.services.async_call("switch", "turn_off", {"entity_id": connect}, blocking=True)
        disconnect.assert_awaited_once()
