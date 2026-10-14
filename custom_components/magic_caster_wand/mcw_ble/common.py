"""Shared data and command builders for MCW and MCB devices."""

import dataclasses
import logging

from .macros import LedGroup, Macro

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BLEData:
    """Response data with information about the Magic Caster Wand device."""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    model: str = ""
    serial_number: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(default_factory=lambda: {})


# A duration of 0 means "hold indefinitely"; the wire format has no such value,
# so it is sent as the maximum the 16-bit duration field can hold.
HOLD_DURATION_MS = 65535


def resolve_led_group(group_val: object) -> LedGroup:
    """Resolve an LED group given either its index or its name."""
    if isinstance(group_val, LedGroup):
        return group_val
    if isinstance(group_val, int):
        return LedGroup(group_val)
    return LedGroup[str(group_val).upper()]


def _clamp_duration(duration: int, what: str) -> int:
    """Fit a duration into the 16-bit field the wire format uses.

    Durations are packed as '<H'. Without this, an out-of-range value raises
    struct.error at send time -- after the macro has been built -- which would
    discard the whole sequence rather than just the offending value.
    """
    clamped = max(0, min(HOLD_DURATION_MS, duration))
    if clamped != duration:
        _LOGGER.warning("%s duration %d ms out of range, using %d ms", what, duration, clamped)
    return clamped


def build_macro(commands: list) -> Macro:
    """Build a Macro from the command list accepted by the send_macro service.

    Each command is either a mapping with a single command key (``{"delay": 100}``)
    or, for commands that take no argument, the bare command name (``"clear"``).
    Unknown commands are logged and skipped so one bad entry does not discard
    the whole sequence.
    """
    macro = Macro()

    for cmd in commands:
        if isinstance(cmd, str):
            key, value = cmd, None
        elif isinstance(cmd, dict) and len(cmd) == 1:
            key, value = next(iter(cmd.items()))
        else:
            _LOGGER.warning("Skipping malformed macro command: %r", cmd)
            continue

        try:
            if key == "changeled":
                params = value or {}
                group = resolve_led_group(params.get("group", "TIP"))
                r, g, b = params.get("rgb", (255, 255, 255))
                duration = int(params.get("duration", 800)) or HOLD_DURATION_MS
                macro.add_led(group, int(r), int(g), int(b), _clamp_duration(duration, "changeled"))
            elif key == "clear":
                macro.add_clear()
            elif key == "delay":
                macro.add_delay(_clamp_duration(int(value), "delay"))
            elif key == "buzz":
                macro.add_buzz(_clamp_duration(int(value), "buzz"))
            elif key == "loop":
                macro.add_loop()
            elif key == "set_loops":
                macro.add_set_loops(int(value))
            elif key == "wait":
                macro.add_wait()
            else:
                _LOGGER.warning("Skipping unknown macro command: %r", key)
        except (KeyError, ValueError, TypeError) as err:
            _LOGGER.warning("Skipping invalid macro command %r: %s", cmd, err)

    return macro


def build_set_led_macro(group: LedGroup, r: int, g: int, b: int, duration: int = 0) -> Macro:
    """Build the macro behind the set_led service.

    A non-zero duration fades the LED in and then clears it, so the colour lasts
    exactly that long. A duration of 0 holds the colour until it is cleared.
    """
    hold = duration == 0
    fade = HOLD_DURATION_MS if hold else _clamp_duration(duration, "set_led")
    macro = Macro().add_led(group, r, g, b, fade)
    if not hold:
        macro.add_wait().add_clear()
    return macro
