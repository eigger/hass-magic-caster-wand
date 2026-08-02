"""Parser for Mcw BLE advertisements."""


def _running_imuvisualizer_via_m() -> bool:
    import inspect
    import sys

    # Check runpy's stack frames for the module name being executed.
    # When python -m is used, runpy imports the package before __main__.__spec__
    # is set, so we look for the 'mod_name' local variable in runpy's frames.
    for frame_record in inspect.getouterframes(sys._getframe()):
        frame = frame_record.frame
        if "runpy" in frame.f_code.co_filename:
            mod_name = frame.f_locals.get("mod_name")
            if mod_name == f"{__name__}.imuvisualizer":
                return True

    return False


if _running_imuvisualizer_via_m():
    __all__ = []
else:
    from .macros import Macro, get_spell_macro
    from .mcb import LIDSTATE
    from .mcw import LedGroup
    from .parser import (
        BLEData,
        McbBluetoothDeviceData,
        McbDevice,
        McwBluetoothDeviceData,
        McwDevice,
        resolve_led_group,
    )

    __all__ = [
        "McwDevice",
        "McbDevice",
        "BLEData",
        "McwBluetoothDeviceData",
        "McbBluetoothDeviceData",
        "LedGroup",
        "Macro",
        "get_spell_macro",
        "resolve_led_group",
        "LIDSTATE",
    ]
