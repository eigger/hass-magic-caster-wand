"""Every service targets the whole integration, so both device types must answer it.

services.yaml scopes each service to `integration: magic_caster_wand`, which means
the UI lets the user pick a box for any of them. A method that only exists on
McwDevice therefore raises AttributeError when the service runs against a box.
"""

import ast
import asyncio
import pathlib

import pytest

from custom_components.magic_caster_wand.mcw_ble.macros import LedGroup
from custom_components.magic_caster_wand.mcw_ble.parser import McbDevice, McwDevice, resolve_led_group

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "magic_caster_wand"

# service name -> the device method its handler calls
SERVICE_METHODS = {
    "vibrate": "buzz",
    "set_led": "set_led",
    "clear_leds": "clear_leds",
    "play_spell": "send_macro",
    "send_macro": "send_macro_parse",
}


def registered_services():
    """Service names passed to hass.services.async_register in __init__.py."""
    tree = ast.parse((COMPONENT / "__init__.py").read_text())
    found = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "async_register"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
        ):
            found.add(node.args[1].value)
    return found


def test_every_registered_service_is_covered_by_this_test():
    assert registered_services() == set(SERVICE_METHODS), (
        "a service was added or renamed; update SERVICE_METHODS so the box coverage check stays honest"
    )


@pytest.mark.parametrize(("service", "method"), sorted(SERVICE_METHODS.items()))
@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_both_device_types_answer_every_service(service, method, device_cls):
    device = device_cls("AA:BB:CC:DD:EE:FF")

    assert hasattr(device, method), (
        f"{device_cls.__name__} has no {method}(), so `{service}` would raise AttributeError"
    )


def test_vibrating_a_box_is_a_harmless_no_op():
    """The box has no vibration motor; the call must not raise."""
    box = McbDevice("AA:BB:CC:DD:EE:FF")

    asyncio.run(box.buzz(500))


def test_disconnected_devices_ignore_service_calls():
    """Nothing is connected in these tests, so no call may reach a None client."""
    for device in (McwDevice("AA:BB:CC:DD:EE:FF"), McbDevice("AA:BB:CC:DD:EE:FF")):
        asyncio.run(device.set_led(LedGroup.TIP, 1, 2, 3, 100))
        asyncio.run(device.clear_leds())
        asyncio.run(device.send_macro_parse([{"clear": None}]))


# ── LED group resolution used by the set_led service ─────────────────────────


@pytest.mark.parametrize("value", ["TIP", "tip", "Tip", 0, LedGroup.TIP])
def test_set_led_group_accepts_the_forms_a_script_may_send(value):
    """Scripts and automations bypass selector validation, so casing varies."""
    assert resolve_led_group(value) is LedGroup.TIP


@pytest.mark.parametrize("value", ["NOT_A_GROUP", 99, None])
def test_set_led_group_rejects_nonsense(value):
    with pytest.raises((KeyError, ValueError)):
        resolve_led_group(value)


def test_selector_options_all_resolve():
    """Every option offered in services.yaml must map to a real LED group."""
    text = (COMPONENT / "services.yaml").read_text()
    options = [line.split("value:")[1].strip() for line in text.splitlines() if "value:" in line]

    assert options, "no selector options found in services.yaml"
    for option in options:
        resolve_led_group(option)
