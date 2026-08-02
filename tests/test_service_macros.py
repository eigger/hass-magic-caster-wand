"""Tests for the command list accepted by the send_macro and set_led services."""

import struct

import pytest

from custom_components.magic_caster_wand.mcw_ble.macros import MACROIDS, LedGroup
from custom_components.magic_caster_wand.mcw_ble.parser import (
    HOLD_DURATION_MS,
    build_macro,
    build_set_led_macro,
)


def opcodes(macro):
    """The macro's command opcodes, without the CONTROL frame byte."""
    return [cmd.to_bytes()[0] for cmd in macro.commands]


# ── Command forms ────────────────────────────────────────────────────────────


def test_mapping_commands_are_built_in_order():
    macro = build_macro(
        [
            {"set_loops": 2},
            {"changeled": {"group": "TIP", "rgb": [1, 2, 3], "duration": 100}},
            {"delay": 50},
            {"buzz": 20},
            {"wait": None},
            {"clear": None},
            {"loop": None},
        ]
    )

    assert opcodes(macro) == [
        MACROIDS.SET_LOOPS,
        MACROIDS.LIGHT_CONTROL_TRANSITION,
        MACROIDS.DELAY,
        MACROIDS.HAP_BUZZ,
        MACROIDS.WAIT_BUSY,
        MACROIDS.LIGHT_CONTROL_CLEAR_ALL,
        MACROIDS.SET_LOOP,
    ]


def test_bare_string_commands_are_accepted():
    """`- clear` in YAML parses to a string, not a single-key mapping."""
    macro = build_macro(["clear", "wait", "loop"])

    assert opcodes(macro) == [
        MACROIDS.LIGHT_CONTROL_CLEAR_ALL,
        MACROIDS.WAIT_BUSY,
        MACROIDS.SET_LOOP,
    ]


def test_string_and_mapping_forms_are_equivalent():
    assert build_macro(["clear"]).to_bytes() == build_macro([{"clear": None}]).to_bytes()


def test_empty_command_list_yields_empty_macro():
    assert build_macro([]).commands == []


# ── changeled ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "group_val", ["POMMEL", "pommel", "Pommel", 3, LedGroup.POMMEL]
)
def test_led_group_accepts_names_indices_and_enums(group_val):
    macro = build_macro([{"changeled": {"group": group_val, "rgb": [0, 0, 0]}}])

    assert macro.commands[0].group == LedGroup.POMMEL


def test_changeled_defaults_to_white_tip():
    macro = build_macro([{"changeled": {}}])
    cmd = macro.commands[0]

    assert (cmd.group, cmd.red, cmd.green, cmd.blue) == (LedGroup.TIP, 255, 255, 255)
    assert cmd.duration_ms == 800


def test_zero_duration_is_sent_as_hold():
    """0 means "hold indefinitely"; the wire field has no such value."""
    macro = build_macro([{"changeled": {"group": "TIP", "duration": 0}}])

    assert macro.commands[0].duration_ms == HOLD_DURATION_MS


def test_string_rgb_and_duration_are_coerced():
    macro = build_macro([{"changeled": {"rgb": ["1", "2", "3"], "duration": "400"}}])
    cmd = macro.commands[0]

    assert (cmd.red, cmd.green, cmd.blue, cmd.duration_ms) == (1, 2, 3, 400)


# ── Malformed input is skipped, not fatal ────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        {"nosuchcommand": 1},
        {"changeled": {"group": "NOT_A_GROUP"}},
        {"changeled": {"group": 99}},
        {"delay": "not a number"},
        {"set_loops": None},
        {"delay": 1, "buzz": 2},
        None,
        42,
        [],
    ],
)
def test_bad_command_is_skipped_without_discarding_the_rest(bad):
    macro = build_macro([{"clear": None}, bad, {"wait": None}])

    assert opcodes(macro) == [MACROIDS.LIGHT_CONTROL_CLEAR_ALL, MACROIDS.WAIT_BUSY]


def test_all_bad_commands_yield_an_empty_macro():
    assert build_macro([{"nope": 1}, None]) .commands == []


# ── set_led ──────────────────────────────────────────────────────────────────


def test_set_led_with_duration_fades_then_clears():
    macro = build_set_led_macro(LedGroup.TIP, 10, 20, 30, duration=500)

    assert opcodes(macro) == [
        MACROIDS.LIGHT_CONTROL_TRANSITION,
        MACROIDS.WAIT_BUSY,
        MACROIDS.LIGHT_CONTROL_CLEAR_ALL,
    ]
    assert macro.commands[0].duration_ms == 500


def test_set_led_without_duration_holds_the_colour():
    macro = build_set_led_macro(LedGroup.TIP, 10, 20, 30, duration=0)

    assert opcodes(macro) == [MACROIDS.LIGHT_CONTROL_TRANSITION]
    assert macro.commands[0].duration_ms == HOLD_DURATION_MS


def test_set_led_duration_defaults_to_hold():
    assert (
        build_set_led_macro(LedGroup.TIP, 1, 2, 3).to_bytes()
        == build_set_led_macro(LedGroup.TIP, 1, 2, 3, duration=0).to_bytes()
    )


def test_set_led_encodes_the_requested_colour():
    payload = build_set_led_macro(LedGroup.MID_LOWER, 9, 8, 7, duration=250).to_bytes()

    assert payload[0] == MACROIDS.CONTROL
    assert payload[1] == MACROIDS.LIGHT_CONTROL_TRANSITION
    assert payload[2] == LedGroup.MID_LOWER
    assert payload[3:6] == bytes([9, 8, 7])
    assert struct.unpack("<H", payload[6:8])[0] == 250
