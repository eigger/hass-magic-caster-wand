"""All entities of one physical device must report the same device name.

Every platform builds DeviceInfo with the same ``connections`` key, so Home
Assistant merges them into a single device. If the platforms disagree on the
name, the one that wins is whichever registers first -- which made a Magic
Caster Box show up named "Magic Caster Wand", because sensor is the first
platform in PLATFORMS and its battery sensors are shared between both devices.
"""

import ast
import pathlib

import pytest

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "magic_caster_wand"
PLATFORMS = sorted(
    p.name for p in COMPONENT.glob("*.py") if p.name not in {"__init__.py", "const.py", "config_flow.py"}
)


def _module(filename):
    return ast.parse((COMPONENT / filename).read_text())


def device_name_by_class(filename):
    """Map each entity class to the `name=` expression of its DeviceInfo, following bases."""
    tree = _module(filename)
    direct, bases = {}, {}
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        bases[cls.name] = [b.id for b in cls.bases if isinstance(b, ast.Name)]
        for node in ast.walk(cls):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "DeviceInfo":
                for kw in node.keywords:
                    if kw.arg == "name":
                        direct[cls.name] = ast.unparse(kw.value)

    def resolve(name, seen=()):
        if name in direct:
            return direct[name]
        for base in bases.get(name, []):
            if base in seen:
                continue
            found = resolve(base, (*seen, name))
            if found:
                return found
        return None

    return {cls: resolve(cls) for cls in bases}


def classes_created_for_a_box(filename):
    """Entity classes instantiated outside an `if device_type == "mcw"` guard."""
    tree = _module(filename)
    setup = next(
        (
            n
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "async_setup_entry"
        ),
        None,
    )
    if setup is None:
        return set()

    declared = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    found = set()

    def walk(stmts, mcw_only):
        for st in stmts:
            if isinstance(st, ast.If):
                test = ast.unparse(st.test)
                walk(st.body, mcw_only or "'mcw'" in test or '"mcw"' in test)
                walk(st.orelse, mcw_only)
            elif not mcw_only:
                for n in ast.walk(st):
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in declared:
                        found.add(n.func.id)

    walk(setup.body, False)
    return found


@pytest.mark.parametrize("filename", PLATFORMS)
def test_entities_shared_with_the_box_do_not_hardcode_wand(filename):
    names = device_name_by_class(filename)
    offenders = {
        cls: names[cls]
        for cls in classes_created_for_a_box(filename)
        if names.get(cls) and "Magic Caster Wand" in names[cls]
    }

    assert not offenders, (
        f"{filename}: {sorted(offenders)} are created for a box but name the device "
        f"{sorted(offenders.values())}; the name must depend on the device type"
    )


def test_wand_only_entities_may_hardcode_wand():
    """Guard against the check above being vacuous: wand-only classes still exist."""
    hardcoding = [
        (f, cls)
        for f in PLATFORMS
        for cls, name in device_name_by_class(f).items()
        if name and "Magic Caster Wand" in name
    ]

    assert hardcoding, "no class hardcodes the wand name any more -- this test is now vacuous"


def test_every_device_name_uses_the_shared_prefix():
    for filename in PLATFORMS:
        for cls, name in device_name_by_class(filename).items():
            if name is not None:
                assert "Magic Caster" in name, f"{filename}.{cls}: unexpected device name {name}"
