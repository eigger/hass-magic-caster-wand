"""Wand button updates through real HA binary sensor entities."""


async def test_button_press_and_release(hass, loaded_wand):
    runtime, entity_id = loaded_wand
    button = entity_id("binary_sensor", "button_1")
    runtime.buttons_coordinator.async_set_updated_data({"button_1": True})
    await hass.async_block_till_done()
    assert hass.states.get(button).state == "on"
    runtime.buttons_coordinator.async_set_updated_data({"button_1": False})
    await hass.async_block_till_done()
    assert hass.states.get(button).state == "off"
