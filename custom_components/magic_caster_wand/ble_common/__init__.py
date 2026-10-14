"""BLE implementation details shared by Magic Caster Wand and Box."""

from .common import HOLD_DURATION_MS, BLEData, build_macro, build_set_led_macro, resolve_led_group
from .macros import (
    MACROIDS,
    BuzzCommand,
    ChangeLedCommand,
    ClearLedsCommand,
    DelayCommand,
    LedGroup,
    LoopCommand,
    Macro,
    SetLoopsCommand,
    WaitBusyCommand,
)

__all__ = [
    "BLEData",
    "HOLD_DURATION_MS",
    "MACROIDS",
    "BuzzCommand",
    "ChangeLedCommand",
    "ClearLedsCommand",
    "DelayCommand",
    "LedGroup",
    "LoopCommand",
    "Macro",
    "SetLoopsCommand",
    "WaitBusyCommand",
    "build_macro",
    "build_set_led_macro",
    "resolve_led_group",
]
