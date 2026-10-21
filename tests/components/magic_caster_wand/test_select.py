"""Casting color selection through real HA service validation."""

import pytest
from homeassistant.exceptions import HomeAssistantError


async def test_casting_color_and_invalid_option(hass, loaded_wand):
    runtime, entity_id = loaded_wand
    color = entity_id("select", "casting_led_color")
    await hass.services.async_call("select", "select_option", {"entity_id": color, "option": "Red"}, blocking=True)
    assert hass.states.get(color).state == "Red"
    assert runtime.device.casting_led_color == (255, 0, 0)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select", "select_option", {"entity_id": color, "option": "invalid-color"}, blocking=True
        )
    assert hass.states.get(color).state == "Red"
