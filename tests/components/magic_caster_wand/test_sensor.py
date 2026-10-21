"""Battery updates through loaded HA sensor entities."""


async def test_battery_zero_is_reported(hass, loaded_wand):
    runtime, entity_id = loaded_wand
    runtime.connection_coordinator.async_set_updated_data(True)
    battery = entity_id("sensor", "battery")
    runtime.battery_coordinator.async_set_updated_data(72)
    await hass.async_block_till_done()
    assert hass.states.get(battery).state == "72"
    runtime.battery_coordinator.async_set_updated_data(0)
    await hass.async_block_till_done()
    assert hass.states.get(battery).state == "0"
