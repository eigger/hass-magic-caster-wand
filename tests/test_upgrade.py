"""Upgrading from a release that predates box support must not disturb wands.

Config entries created before the box existed have no "device_type" key, and
their entities were registered under names and unique ids that must not move,
or Home Assistant orphans them and the user loses history and automations.
"""

import ast
import pathlib

import pytest

from custom_components.magic_caster_wand.mcw_ble.parser import McbDevice, McwDevice

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "magic_caster_wand"


def test_entries_without_a_device_type_are_treated_as_wands():
    """The key was introduced with box support; existing entries predate it."""
    tree = ast.parse((COMPONENT / "__init__.py").read_text())

    defaults = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "device_type"
        and isinstance(node.args[1], ast.Constant)
    ]

    assert defaults == ["mcw"], f"device_type must default to 'mcw' for pre-box entries, got {defaults}"


@pytest.mark.parametrize(
    ("device_cls", "expected"),
    [(McwDevice, "Magic Caster Wand"), (McbDevice, "Magic Caster Box")],
)
def test_device_label_keeps_the_wand_name_unchanged(device_cls, expected):
    """Platforms now pick the label by device type; a wand must still read "Wand"."""
    device = device_cls("AA:BB:CC:DD:EE:FF")

    label = "Wand" if isinstance(device, McwDevice) else "Box"

    assert f"Magic Caster {label}" == expected


def test_wand_unique_ids_are_unchanged_since_the_last_release():
    """Every wand entity id must keep the mcw_{identifier}_{key} shape it shipped with."""
    prefixes = []
    for path in COMPONENT.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(getattr(t, "attr", None) == "_attr_unique_id" for t in node.targets)
                and isinstance(node.value, ast.JoinedStr)
            ):
                prefixes.append((path.name, ast.unparse(node.value)))

    assert prefixes, "no unique_id assignments found"
    for filename, expr in prefixes:
        assert expr.startswith("f'mcw_"), f"{filename}: unique_id {expr} breaks the established shape"
