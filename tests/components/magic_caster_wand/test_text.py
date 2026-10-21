"""Alias editing uses a real HA text entity and validates its length."""

import pytest


async def test_alias_and_length_limit(hass, loaded_wand):
    _, entity_id = loaded_wand
    alias = entity_id("text", "alias")
    await hass.services.async_call("text", "set_value", {"entity_id": alias, "value": "My wand"}, blocking=True)
    assert hass.states.get(alias).state == "My wand"
    with pytest.raises(ValueError, match="too long"):
        await hass.services.async_call("text", "set_value", {"entity_id": alias, "value": "x" * 33}, blocking=True)
    assert hass.states.get(alias).state == "My wand"
