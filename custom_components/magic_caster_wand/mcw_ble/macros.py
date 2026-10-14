"""Wand spell macros and shared macro compatibility exports."""

from ..common_ble.macros import (
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
from .spells import SPELL_MAP


def get_spell_macro(spell_name: str) -> Macro | None:
    """Get the macro for a named wand spell."""
    name = spell_name.lower().replace(" ", "_").replace("-", "_")
    if spell := SPELL_MAP.get(name):
        return spell.payoff()
    return None


__all__ = [
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
    "get_spell_macro",
]
