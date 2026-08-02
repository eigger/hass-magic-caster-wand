"""Connection and background-task lifecycle."""

import ast
import asyncio
import pathlib

import pytest

from custom_components.magic_caster_wand.mcw_ble.parser import McbDevice, McwDevice

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "magic_caster_wand"


# ── The model probe must not drop a connection the user opened ───────────────


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_model_probe_leaves_an_open_connection_alone(device_cls):
    """connect() returns True for an existing connection without reaching its model
    fetch, so probing that way would drop the user's connection and gain nothing."""
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = ""  # falsy: the device never reported an id
    device.is_connected = lambda: True

    calls = []

    async def fake_connect(ble):
        calls.append("connect")
        return True

    async def fake_disconnect():
        calls.append("disconnect")

    async def fake_refresh():
        calls.append("refresh_model")

    device.connect = fake_connect
    device.disconnect = fake_disconnect
    device._refresh_model = fake_refresh

    asyncio.run(device.update_device(object()))

    assert "disconnect" not in calls, "the model probe must not drop an open connection"


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_model_is_still_fetched_while_connected(device_cls):
    """The point of the probe is to learn the model; staying connected must not
    mean giving that up."""
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = ""
    device.is_connected = lambda: True

    calls = []

    async def fake_refresh():
        calls.append("refresh_model")

    device._refresh_model = fake_refresh
    device.connect = lambda ble: pytest.fail("must not reconnect while already connected")

    asyncio.run(device.update_device(object()))

    assert calls == ["refresh_model"]


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_refresh_model_is_a_no_op_once_known(device_cls):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "WBMC22G1SHNW"

    # No client is attached, so any actual request would raise.
    asyncio.run(device._refresh_model())

    assert device.model == "WBMC22G1SHNW"


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_refresh_model_without_a_client_is_safe(device_cls):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = None

    asyncio.run(device._refresh_model())

    assert device.model is None


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_model_probe_runs_when_disconnected_and_model_unknown(device_cls):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = None
    device.is_connected = lambda: False

    calls = []

    async def fake_connect(ble):
        calls.append("connect")
        return True

    async def fake_disconnect():
        calls.append("disconnect")

    device.connect = fake_connect
    device.disconnect = fake_disconnect

    asyncio.run(device.update_device(object()))

    assert calls == ["connect", "disconnect"]


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
def test_no_probe_once_the_model_is_known(device_cls):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "WBMC22G1SHNW"
    device.is_connected = lambda: False
    device.connect = lambda ble: pytest.fail("must not reconnect once the model is known")

    asyncio.run(device.update_device(object()))


# ── Background tasks are tracked and cancelled ───────────────────────────────


def test_spawned_tasks_are_referenced_until_they_finish():
    """The event loop holds only a weak reference, so an untracked task can be
    garbage collected mid-flight."""
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    started = asyncio.Event()

    async def scenario():
        async def work():
            started.set()
            await asyncio.sleep(0.05)

        device._spawn(work())
        await started.wait()
        assert len(device._background_tasks) == 1

        await asyncio.sleep(0.1)
        assert device._background_tasks == set(), "finished tasks must be released"

    asyncio.run(scenario())


def test_disconnect_cancels_pending_background_work():
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    device._spell_timeout = 3600
    finished = []

    async def scenario():
        async def never_finishes():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                finished.append("cancelled")
                raise

        device._spawn(never_finishes())
        device._schedule_spell_reset()
        await asyncio.sleep(0)

        assert device._background_tasks
        assert device._spell_reset_timeout_task is not None

        await device.disconnect()

        assert device._background_tasks == set()
        assert device._spell_reset_timeout_task is None
        assert finished == ["cancelled"]

    asyncio.run(scenario())


def test_spawn_is_used_instead_of_bare_create_task():
    """Guard against a new fire-and-forget task being added without tracking."""
    tree = ast.parse((COMPONENT / "mcw_ble" / "parser.py").read_text())
    bare = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "create_task"
    ]

    # Only the two deliberate ones: the helper itself and the cancellable
    # spell-reset task, which is stored in its own attribute.
    assert len(bare) == 2, f"untracked asyncio.create_task at lines {bare}; use self._spawn()"


# ── Services are removed with the last entry ─────────────────────────────────


def test_unload_removes_every_registered_service():
    source = (COMPONENT / "__init__.py").read_text()
    tree = ast.parse(source)

    registered = {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "async_register"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
    }
    services_const = next(n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "SERVICES")
    declared = {e.value for e in services_const.elts}

    assert "async_remove" in source, "services are never removed on unload"
    assert declared == registered or not registered, (
        f"SERVICES {sorted(declared)} does not match what is registered {sorted(registered)}"
    )
