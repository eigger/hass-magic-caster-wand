"""Macro System for Magic Caster Wand BLE."""

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Union

class LedGroup(IntEnum):
    """LED groups on the wand."""
    TIP = 0
    MID_UPPER = 1
    MID_LOWER = 2
    POMMEL = 3

# Macro packet IDs from APK
class MACROIDS:
    DELAY = 0x10
    """MacroDelayMessage.kt"""
    WAIT_BUSY = 0x11
    """MacroWaitBusyMessage.kt"""
    LIGHT_CONTROL_CLEAR_ALL = 0x20
    """MacroLightControlClearAllMessage.kt"""
    LIGHT_CONTROL_TRANSITION = 0x22
    """MacroLightControlTransitionMessage.kt"""
    HAP_BUZZ = 0x50
    """MacroHapBuzzMessage.kt"""
    FLUSH = 0x60
    """MacroFlushMessage.kt"""
    CONTROL = 0x68
    """MacroControlMessage.kt"""
    SET_LOOPS = 0x80
    """MacroSetLoopsMessage.kt"""
    SET_LOOP = 0x81
    """MacroSetLoopMessage.kt"""

@dataclass
class ChangeLedCommand:
    """Change LED color on a specific group."""
    group: LedGroup
    red: int
    green: int
    blue: int
    duration_ms: int
    
    def to_bytes(self) -> bytes:
        return bytes([
            MACROIDS.LIGHT_CONTROL_TRANSITION,
            int(self.group),
            self.red & 0xFF,
            self.green & 0xFF,
            self.blue & 0xFF,
        ]) + struct.pack('<H', self.duration_ms)

@dataclass
class ClearLedsCommand:
    """Clear all LEDs."""
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.LIGHT_CONTROL_CLEAR_ALL])

@dataclass
class DelayCommand:
    """Add a delay in the macro sequence."""
    duration_ms: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.DELAY]) + struct.pack('<H', self.duration_ms)

@dataclass
class BuzzCommand:
    """Vibrate the wand."""
    duration_ms: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.HAP_BUZZ]) + struct.pack('<H', self.duration_ms)

@dataclass
class LoopCommand:
    """Mark the start of a loop."""
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.SET_LOOP])

@dataclass
class SetLoopsCommand:
    """Set the number of loop iterations."""
    loops: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.SET_LOOPS, self.loops & 0xFF])

@dataclass
class WaitBusyCommand:
    """Wait for previous commands to complete."""
    def to_bytes(self) -> bytes:
        return bytes([MACROIDS.WAIT_BUSY])

MacroCommandType = Union[
    ChangeLedCommand, ClearLedsCommand, DelayCommand,
    BuzzCommand, LoopCommand, SetLoopsCommand, WaitBusyCommand
]

@dataclass
class Macro:
    """A sequence of macro commands."""
    commands: List[MacroCommandType] = field(default_factory=list)
    
    def add_led(self, group: LedGroup, red: int, green: int, blue: int, duration_ms: int) -> 'Macro':
        self.commands.append(ChangeLedCommand(group, red, green, blue, duration_ms))
        return self
    
    def add_led_hex(self, group: LedGroup, hex_color: str, duration_ms: int) -> 'Macro':
        color = hex_color.lstrip('#')
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return self.add_led(group, r, g, b, duration_ms)

    def add_clear(self) -> 'Macro':
        self.commands.append(ClearLedsCommand())
        return self
    
    def add_delay(self, duration_ms: int) -> 'Macro':
        self.commands.append(DelayCommand(duration_ms))
        return self
    
    def add_buzz(self, duration_ms: int) -> 'Macro':
        self.commands.append(BuzzCommand(duration_ms))
        return self
    
    def add_loop(self) -> 'Macro':
        self.commands.append(LoopCommand())
        return self
    
    def add_set_loops(self, count: int) -> 'Macro':
        self.commands.append(SetLoopsCommand(count))
        return self
    
    def add_wait(self) -> 'Macro':
        self.commands.append(WaitBusyCommand())
        return self
    
    def to_bytes(self) -> bytes:
        data = bytearray()
        for cmd in self.commands:
            data.extend(cmd.to_bytes())
        return bytes([MACROIDS.CONTROL]) + bytes(data)

def get_spell_macro(spell_name: str) -> Optional[Macro]:
    """Get a macro for a spell by name."""
    from .spells import SPELL_MAP
    name = spell_name.lower().replace(' ', '_').replace('-', '_')
    if name in SPELL_MAP:
        return SPELL_MAP[name].payoff()
    return None