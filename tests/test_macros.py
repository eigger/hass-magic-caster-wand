"""Tests for the macro wire format."""

import struct

import pytest

from custom_components.magic_caster_wand.mcw_ble.macros import (
    MACROIDS,
    LedGroup,
    Macro,
    get_spell_macro,
)


def test_change_led_encoding():
    payload = Macro().add_led(LedGroup.MID_UPPER, 10, 20, 30, 800).to_bytes()

    assert payload[0] == MACROIDS.CONTROL
    assert payload[1] == MACROIDS.LIGHT_CONTROL_TRANSITION
    assert payload[2] == LedGroup.MID_UPPER
    assert payload[3:6] == bytes([10, 20, 30])
    assert struct.unpack("<H", payload[6:8])[0] == 800


def test_change_led_masks_out_of_range_channels():
    payload = Macro().add_led(LedGroup.TIP, 300, -1, 255, 0).to_bytes()

    assert payload[3:6] == bytes([300 & 0xFF, -1 & 0xFF, 255])


def test_led_hex_matches_rgb():
    assert (
        Macro().add_led_hex(LedGroup.TIP, "#FF8000", 500).to_bytes()
        == Macro().add_led(LedGroup.TIP, 255, 128, 0, 500).to_bytes()
    )


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (lambda m: m.add_clear(), bytes([MACROIDS.LIGHT_CONTROL_CLEAR_ALL])),
        (lambda m: m.add_wait(), bytes([MACROIDS.WAIT_BUSY])),
        (lambda m: m.add_loop(), bytes([MACROIDS.SET_LOOP])),
        (lambda m: m.add_delay(250), bytes([MACROIDS.DELAY]) + struct.pack("<H", 250)),
        (lambda m: m.add_buzz(100), bytes([MACROIDS.HAP_BUZZ]) + struct.pack("<H", 100)),
        (lambda m: m.add_set_loops(3), bytes([MACROIDS.SET_LOOPS, 3])),
    ],
)
def test_single_command_encoding(build, expected):
    assert build(Macro()).to_bytes() == bytes([MACROIDS.CONTROL]) + expected


def test_empty_macro_is_bare_control_opcode():
    assert Macro().to_bytes() == bytes([MACROIDS.CONTROL])


def test_commands_are_emitted_in_order():
    payload = Macro().add_set_loops(2).add_led(LedGroup.TIP, 1, 2, 3, 100).add_wait().add_clear().add_loop().to_bytes()

    assert payload == (
        bytes([MACROIDS.CONTROL])
        + bytes([MACROIDS.SET_LOOPS, 2])
        + bytes([MACROIDS.LIGHT_CONTROL_TRANSITION, LedGroup.TIP, 1, 2, 3])
        + struct.pack("<H", 100)
        + bytes([MACROIDS.WAIT_BUSY])
        + bytes([MACROIDS.LIGHT_CONTROL_CLEAR_ALL])
        + bytes([MACROIDS.SET_LOOP])
    )


def test_builders_are_chainable_on_one_instance():
    macro = Macro()
    assert macro.add_clear() is macro
    assert macro.add_wait() is macro
    assert len(macro.commands) == 2


def test_get_spell_macro_normalises_name():
    macro = get_spell_macro("Wingardium Leviosa")
    if macro is None:
        pytest.skip("spell not present in SPELL_MAP")

    assert get_spell_macro("wingardium-leviosa") is not None
    assert get_spell_macro("wingardium_leviosa") is not None


def test_get_spell_macro_unknown_returns_none():
    assert get_spell_macro("not a real spell") is None
