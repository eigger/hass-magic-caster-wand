"""Macro System for Magic Caster Wand BLE."""

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Union

class LedGroup(IntEnum):
    """LED groups on the wand."""
    TIP = 0
    POMMEL = 1
    MID_LOWER = 2
    MID_UPPER = 3

# Macro packet IDs from APK
MACRO_ID_CHANGE_LED = 0x42
MACRO_ID_CLEAR_LEDS = 0x40
MACRO_ID_DELAY = 0x44
MACRO_ID_BUZZ = 0x46
MACRO_ID_LOOP = 0x48
MACRO_ID_SET_LOOPS = 0x4A
MACRO_ID_WAIT_BUSY = 0x4C
MACRO_ID_MACRO_CONTROL = 0x68

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
            MACRO_ID_CHANGE_LED,
            int(self.group),
            self.red & 0xFF,
            self.green & 0xFF,
            self.blue & 0xFF,
        ]) + struct.pack('>H', self.duration_ms)

@dataclass
class ClearLedsCommand:
    """Clear all LEDs."""
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_CLEAR_LEDS])

@dataclass
class DelayCommand:
    """Add a delay in the macro sequence."""
    duration_ms: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_DELAY]) + struct.pack('>H', self.duration_ms)

@dataclass
class BuzzCommand:
    """Vibrate the wand."""
    duration_ms: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_BUZZ]) + struct.pack('>H', self.duration_ms)

@dataclass
class LoopCommand:
    """Mark the start of a loop."""
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_LOOP])

@dataclass
class SetLoopsCommand:
    """Set the number of loop iterations."""
    loops: int
    
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_SET_LOOPS, self.loops & 0xFF])

@dataclass
class WaitBusyCommand:
    """Wait for previous commands to complete."""
    def to_bytes(self) -> bytes:
        return bytes([MACRO_ID_WAIT_BUSY])

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
        return bytes([MACRO_ID_MACRO_CONTROL]) + bytes(data)

class SpellMacros:
    """Pre-built macro templates for all spells."""
    
    @staticmethod
    def lumos() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led(LedGroup.TIP, 255, 255, 255, 2000))
    
    @staticmethod
    def nox() -> Macro:
        return (Macro()
            .add_buzz(100)
            .add_led_hex(LedGroup.TIP, "330033", 200)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def verdimillious() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00FF00", 200)
            .add_led_hex(LedGroup.MID_UPPER, "00AA00", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "00FF00", 150)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def vermillious() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "AA0000", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def flagrate() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FF6600", 400)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 300)
            .add_delay(300)
            .add_led_hex(LedGroup.TIP, "FF9900", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def fulgari() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFFF00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF00", 250)
            .add_led_hex(LedGroup.MID_LOWER, "FFFF00", 200)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def incendio() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF4500", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def confringo() -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "FF0000", 100)
            .add_led_hex(LedGroup.MID_UPPER, "FF4500", 100)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 100)
            .add_led_hex(LedGroup.POMMEL, "FFFF00", 100)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def bombarda() -> Macro:
        return (Macro()
            .add_buzz(500)
            .add_led_hex(LedGroup.TIP, "FF4500", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FF4500", 120)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 100)
            .add_led_hex(LedGroup.POMMEL, "FF8800", 80)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def reducto() -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "FF3300", 200)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "FFAA00", 150)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def expulso() -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "FF6600", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFAA00", 200)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def pestis_incendium() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 200)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 200)
            .add_led_hex(LedGroup.POMMEL, "FF9900", 200)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def aguamenti() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "0066FF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "00AAFF", 300)
            .add_delay(200)
            .add_clear())

    @staticmethod
    def glacius() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "00FFFF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "88FFFF", 300)
            .add_led_hex(LedGroup.MID_LOWER, "AAFFFF", 250)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def ventus() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "88CCFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "AADDFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "88CCFF", 200)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def meteolojinx() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "666688", 300)
            .add_led_hex(LedGroup.MID_UPPER, "888899", 250)
            .add_delay(150)
            .add_led_hex(LedGroup.TIP, "FFFF00", 100)
            .add_delay(10)
            .add_clear())
    
    @staticmethod
    def protego() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "0055FF", 500)
            .add_led_hex(LedGroup.MID_UPPER, "0055FF", 400)
            .add_led_hex(LedGroup.MID_LOWER, "0055FF", 300)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def salvio_hexia() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "6666FF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "4444FF", 350)
            .add_led_hex(LedGroup.MID_LOWER, "2222FF", 300)
            .add_led_hex(LedGroup.POMMEL, "0000FF", 250)
            .add_delay(250)
            .add_clear())
    
    @staticmethod
    def finite() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AAAAFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "6666FF", 200)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def impedimenta() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "8888FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "6666DD", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def stupefy() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "880000", 150)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def expelliarmus() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF0000", 150)
            .add_led_hex(LedGroup.POMMEL, "FF0000", 100)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def flipendo() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF6633", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF4422", 150)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def depulso() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF8844", 250)
            .add_led_hex(LedGroup.MID_UPPER, "FF6622", 200)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def petrificus_totalus() -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "CCCCCC", 300)
            .add_led_hex(LedGroup.MID_UPPER, "AAAAAA", 250)
            .add_led_hex(LedGroup.MID_LOWER, "888888", 200)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def immobulus() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "88FFFF", 350)
            .add_led_hex(LedGroup.MID_UPPER, "66DDDD", 300)
            .add_delay(250)
            .add_clear())
    
    @staticmethod
    def silencio() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "9999AA", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def langlock() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AA6666", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def incarcerous() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_led_hex(LedGroup.MID_UPPER, "A0522D", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def brachiabindo() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "996633", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def rictusempra() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAACC", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFCCDD", 200)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def densaugeo() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFCC", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def anteoculatia() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_led_hex(LedGroup.MID_UPPER, "A0522D", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def entomorphis() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "336633", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def calvorio() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFEECC", 200)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def mucus_ad_nauseum() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "66FF66", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def colloshoo() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AA8844", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def melefors() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF8800", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 250)
            .add_delay(200)
            .add_clear())

    @staticmethod
    def expecto_patronum() -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "E0E0FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "C0C0FF", 300)
            .add_led_hex(LedGroup.MID_LOWER, "A0A0FF", 300)
            .add_led_hex(LedGroup.POMMEL, "8080FF", 300)
            .add_delay(500)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 1000)
            .add_delay(500)
            .add_clear())
    
    @staticmethod
    def riddikulus() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFFF00", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF00FF", 200)
            .add_led_hex(LedGroup.MID_LOWER, "00FFFF", 200)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def arania_exumai() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF00", 150)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def avada_kedavra() -> Macro:
        return (Macro()
            .add_buzz(500)
            .add_led_hex(LedGroup.TIP, "00FF00", 100)
            .add_led_hex(LedGroup.MID_UPPER, "00FF00", 100)
            .add_led_hex(LedGroup.MID_LOWER, "00FF00", 100)
            .add_led_hex(LedGroup.POMMEL, "00FF00", 100)
            .add_delay(200)
            .add_clear())

    @staticmethod
    def wingardium_leviosa() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 300)
            .add_delay(200)
            .add_led_hex(LedGroup.TIP, "FFFF66", 300)
            .add_delay(200)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 300)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def locomotor() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "6699FF", 250)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "99AAFF", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def accio() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "6688FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "4466DD", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def ascendio() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.POMMEL, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_LOWER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_UPPER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "AACCFF", 200)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def descendo() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_UPPER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_LOWER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.POMMEL, "6688DD", 200)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def piertotum_locomotor() -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "CCCCCC", 250)
            .add_led_hex(LedGroup.MID_UPPER, "AAAAAA", 250)
            .add_led_hex(LedGroup.MID_LOWER, "888888", 200)
            .add_led_hex(LedGroup.POMMEL, "666666", 150)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def spongify() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFCCFF", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def alohomora() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFD700", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFAA00", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def colloportus() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "886633", 300)
            .add_led_hex(LedGroup.MID_UPPER, "664422", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def aberto() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFDD66", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def finestra() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 150)
            .add_led_hex(LedGroup.MID_UPPER, "CCCCFF", 100)
            .add_delay(100)
            .add_clear())

    @staticmethod
    def evanesco() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "888888", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "444444", 100)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def colovaria() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "00FF00", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "0000FF", 200)
            .add_delay(100)
            .add_clear())
    
    @staticmethod
    def orchideous() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF66FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF99FF", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def herbivicus() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00AA00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "00DD00", 250)
            .add_led_hex(LedGroup.MID_LOWER, "00FF00", 200)
            .add_delay(250)
            .add_clear())
    
    @staticmethod
    def reparo() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFDD88", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFCC66", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def scourgify() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "88DDFF", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def confundo() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFAAFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "AAFFFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 200)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def the_cheering_charm() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFF00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFDD00", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def the_sleeping_charm() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "6666AA", 400)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def sonorus() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAA66", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def quietus() -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "666688", 250)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def cantis() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFCC99", 250)
            .add_led_hex(LedGroup.MID_UPPER, "FFAA88", 20)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def revelio() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF88", 150)
            .add_led_hex(LedGroup.MID_LOWER, "FFFF00", 150)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def appare_vestigium() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFDD00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFCC00", 300)
            .add_delay(300)
            .add_clear())
    
    @staticmethod
    def the_hour_reversal_charm() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFDD88", 200)
            .add_led_hex(LedGroup.MID_UPPER, "DDBB66", 200)
            .add_led_hex(LedGroup.MID_LOWER, "BB9944", 200)
            .add_led_hex(LedGroup.POMMEL, "997722", 200)
            .add_delay(250)
            .add_clear())
    
    @staticmethod
    def the_hour_reversal_reversal_charm() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.POMMEL, "997722", 200)
            .add_led_hex(LedGroup.MID_LOWER, "BB9944", 200)
            .add_led_hex(LedGroup.MID_UPPER, "DDBB66", 200)
            .add_led_hex(LedGroup.TIP, "FFDD88", 200)
            .add_delay(250)
            .add_clear())
    
    @staticmethod
    def the_force_spell() -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "88AAFF", 250)
            .add_led_hex(LedGroup.MID_UPPER, "6688DD", 200)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def the_stretching_jinx() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAA88", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def the_hair_thickening_growing_charm() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def the_pepper_breath_hex() -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF4400", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 250)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def everte_statum() -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF6644", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF4422", 150)
            .add_delay(150)
            .add_clear())
    
    @staticmethod
    def spell_success() -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00FF00", 300)
            .add_delay(200)
            .add_clear())
    
    @staticmethod
    def spell_fail() -> Macro:
        return (Macro()
            .add_buzz(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "000000", 100)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_clear())

# Dictionary mapping spell names to macro methods
SPELL_MACRO_MAP = {
    'the_force_spell': SpellMacros.the_force_spell,
    'colloportus': SpellMacros.colloportus,
    'colloshoo': SpellMacros.colloshoo,
    'the_hour_reversal_reversal_charm': SpellMacros.the_hour_reversal_reversal_charm,
    'evanesco': SpellMacros.evanesco,
    'herbivicus': SpellMacros.herbivicus,
    'orchideous': SpellMacros.orchideous,
    'brachiabindo': SpellMacros.brachiabindo,
    'meteolojinx': SpellMacros.meteolojinx,
    'riddikulus': SpellMacros.riddikulus,
    'silencio': SpellMacros.silencio,
    'immobulus': SpellMacros.immobulus,
    'confringo': SpellMacros.confringo,
    'petrificus_totalus': SpellMacros.petrificus_totalus,
    'flipendo': SpellMacros.flipendo,
    'the_cheering_charm': SpellMacros.the_cheering_charm,
    'salvio_hexia': SpellMacros.salvio_hexia,
    'pestis_incendium': SpellMacros.pestis_incendium,
    'alohomora': SpellMacros.alohomora,
    'protego': SpellMacros.protego,
    'langlock': SpellMacros.langlock,
    'mucus_ad_nauseum': SpellMacros.mucus_ad_nauseum,
    'flagrate': SpellMacros.flagrate,
    'glacius': SpellMacros.glacius,
    'finite': SpellMacros.finite,
    'anteoculatia': SpellMacros.anteoculatia,
    'expelliarmus': SpellMacros.expelliarmus,
    'expecto_patronum': SpellMacros.expecto_patronum,
    'descendo': SpellMacros.descendo,
    'depulso': SpellMacros.depulso,
    'reducto': SpellMacros.reducto,
    'colovaria': SpellMacros.colovaria,
    'aberto': SpellMacros.aberto,
    'confundo': SpellMacros.confundo,
    'densaugeo': SpellMacros.densaugeo,
    'the_stretching_jinx': SpellMacros.the_stretching_jinx,
    'entomorphis': SpellMacros.entomorphis,
    'the_hair_thickening_growing_charm': SpellMacros.the_hair_thickening_growing_charm,
    'bombarda': SpellMacros.bombarda,
    'finestra': SpellMacros.finestra,
    'the_sleeping_charm': SpellMacros.the_sleeping_charm,
    'rictusempra': SpellMacros.rictusempra,
    'piertotum_locomotor': SpellMacros.piertotum_locomotor,
    'expulso': SpellMacros.expulso,
    'impedimenta': SpellMacros.impedimenta,
    'ascendio': SpellMacros.ascendio,
    'incarcerous': SpellMacros.incarcerous,
    'ventus': SpellMacros.ventus,
    'revelio': SpellMacros.revelio,
    'accio': SpellMacros.accio,
    'melefors': SpellMacros.melefors,
    'scourgify': SpellMacros.scourgify,
    'wingardium_leviosa': SpellMacros.wingardium_leviosa,
    'nox': SpellMacros.nox,
    'stupefy': SpellMacros.stupefy,
    'spongify': SpellMacros.spongify,
    'lumos': SpellMacros.lumos,
    'appare_vestigium': SpellMacros.appare_vestigium,
    'verdimillious': SpellMacros.verdimillious,
    'fulgari': SpellMacros.fulgari,
    'reparo': SpellMacros.reparo,
    'locomotor': SpellMacros.locomotor,
    'quietus': SpellMacros.quietus,
    'everte_statum': SpellMacros.everte_statum,
    'incendio': SpellMacros.incendio,
    'aguamenti': SpellMacros.aguamenti,
    'sonorus': SpellMacros.sonorus,
    'cantis': SpellMacros.cantis,
    'arania_exumai': SpellMacros.arania_exumai,
    'calvorio': SpellMacros.calvorio,
    'the_hour_reversal_charm': SpellMacros.the_hour_reversal_charm,
    'vermillious': SpellMacros.vermillious,
    'the_pepper_breath_hex': SpellMacros.the_pepper_breath_hex,
    'avada_kedavra': SpellMacros.avada_kedavra,
    'spell_success': SpellMacros.spell_success,
    'spell_fail': SpellMacros.spell_fail,
}

def get_spell_macro(spell_name: str) -> Optional[Macro]:
    """Get a macro for a spell by name."""
    name = spell_name.lower().replace(' ', '_').replace('-', '_')
    if name in SPELL_MACRO_MAP:
        return SPELL_MACRO_MAP[name]()
    return None
