"""Connection and background-task lifecycle."""

import ast
import asyncio
import pathlib
from contextlib import asynccontextmanager

import pytest

from custom_components.magic_caster_wand.mcw_ble import mcb, parser
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


@pytest.mark.parametrize(("device_cls", "client_name"), [(McwDevice, "McwClient"), (McbDevice, "McbClient")])
def test_connect_failure_releases_partially_initialized_link(device_cls, client_name, monkeypatch):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "known-model"
    calls = []

    class Client:
        is_connected = True

        async def disconnect(self):
            calls.append("disconnect")
            self.is_connected = False

    client = Client()

    class ProtocolClient:
        def __init__(self, ble_client):
            self.client = ble_client

        def register_callback(self, *callbacks):
            pass

        async def start_notify(self):
            raise RuntimeError("notification setup failed")

        async def stop_notify(self):
            calls.append("stop_notify")

    @asynccontextmanager
    async def session(*args, **kwargs):
        yield client
        if client.is_connected:
            await client.disconnect()
            kwargs["disconnected_callback"](client)

    monkeypatch.setattr(parser, "ble_session", session)
    monkeypatch.setattr(parser, client_name, ProtocolClient)

    assert (
        asyncio.run(device.connect(type("BleDevice", (), {"address": "AA:BB:CC:DD:EE:FF", "name": "test"})())) is False
    )
    assert calls == ["stop_notify", "disconnect"]
    assert device.client is None
    assert getattr(device, "_mcw", getattr(device, "_mcb", None)) is None


def test_box_notification_setup_continues_when_initial_battery_read_fails(monkeypatch):
    calls = []

    class Client:
        is_connected = True

        async def start_notify(self, *args):
            calls.append("start_notify")

        async def stop_notify(self, *args):
            calls.append("stop_notify")

        async def read_gatt_char(self, *args):
            raise RuntimeError("battery read failed")

    async def no_sleep(_seconds):
        pass

    async def record_request(name):
        calls.append(name)

    monkeypatch.setattr(mcb, "sleep", no_sleep)
    protocol = mcb.McbClient(Client())
    protocol.request_box_notifications = lambda: record_request("box")
    protocol.request_charge_notifications = lambda: record_request("charge")
    protocol.request_lid_notifications = lambda: record_request("lid")
    protocol.request_lid_status = lambda: record_request("status")

    async def lifecycle():
        await protocol.start_notify()
        await protocol.stop_notify()

    asyncio.run(lifecycle())

    assert calls == ["start_notify", "start_notify", "box", "charge", "lid", "status", "stop_notify", "stop_notify"]


def test_box_notification_setup_propagates_required_state_request_failure(monkeypatch):
    class Client:
        is_connected = True

        async def start_notify(self, *args):
            pass

        async def stop_notify(self, *args):
            pass

        async def read_gatt_char(self, *args):
            return b"\x64"

    async def no_sleep(_seconds):
        pass

    async def fail_request():
        raise RuntimeError("box state request failed")

    monkeypatch.setattr(mcb, "sleep", no_sleep)
    protocol = mcb.McbClient(Client())
    protocol.request_box_notifications = fail_request

    async def lifecycle():
        with pytest.raises(RuntimeError, match="box state request failed"):
            await protocol.start_notify()
        await protocol.stop_notify()

    asyncio.run(lifecycle())


@pytest.mark.parametrize(("device_cls", "client_name"), [(McwDevice, "McwClient"), (McbDevice, "McbClient")])
def test_cancel_during_failed_connect_cleanup_still_disconnects(device_cls, client_name, monkeypatch):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "known-model"
    calls = []

    class Client:
        is_connected = True

        async def disconnect(self):
            calls.append("disconnect")
            self.is_connected = False

    client = Client()

    class ProtocolClient:
        def __init__(self, ble_client):
            self.client = ble_client

        def register_callback(self, *callbacks):
            pass

        async def start_notify(self):
            raise RuntimeError("notification setup failed")

        async def stop_notify(self):
            raise asyncio.CancelledError

    @asynccontextmanager
    async def session(*args, **kwargs):
        yield client
        if client.is_connected:
            await client.disconnect()
            kwargs["disconnected_callback"](client)

    monkeypatch.setattr(parser, "ble_session", session)
    monkeypatch.setattr(parser, client_name, ProtocolClient)

    ble_device = type("BleDevice", (), {"address": "AA:BB:CC:DD:EE:FF", "name": "test"})()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(device.connect(ble_device))

    assert calls == ["disconnect"]
    assert device.client is None
    assert getattr(device, "_mcw", getattr(device, "_mcb", None)) is None


@pytest.mark.parametrize(("device_cls", "client_name"), [(McwDevice, "McwClient"), (McbDevice, "McbClient")])
def test_successful_connection_is_owned_until_device_disconnect(device_cls, client_name, monkeypatch):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "known-model"
    events = []

    class Client:
        is_connected = True

    client = Client()

    @asynccontextmanager
    async def session(*args, **kwargs):
        events.append("enter")
        try:
            yield client
        finally:
            client.is_connected = False
            kwargs["disconnected_callback"](client)
            events.append("exit")

    class ProtocolClient:
        def __init__(self, ble_client):
            self.client = ble_client

        def register_callback(self, *callbacks):
            pass

        async def start_notify(self):
            events.append("start_notify")

        async def stop_notify(self):
            events.append("stop_notify")

        async def imu_streaming_stop(self):
            events.append("stop_stream")

    monkeypatch.setattr(parser, "ble_session", session)
    monkeypatch.setattr(parser, client_name, ProtocolClient)
    ble_device = type("BleDevice", (), {"address": "AA:BB:CC:DD:EE:FF", "name": "test"})()

    async def connection_lifecycle():
        assert await device.connect(ble_device) is True
        assert events == ["enter", "start_notify"]
        assert device._ble_session_stack is not None
        await device.disconnect()

    asyncio.run(connection_lifecycle())
    expected_events = ["enter", "start_notify"]
    if device_cls is McwDevice:
        expected_events.append("stop_stream")
    expected_events.extend(["stop_notify", "exit"])
    assert events == expected_events
    assert device._ble_session_stack is None
    assert device.client is None


@pytest.mark.parametrize("device_cls", [McwDevice, McbDevice])
@pytest.mark.parametrize("stop_error", [RuntimeError("notify stop failed"), asyncio.CancelledError])
def test_disconnect_closes_ble_session_when_stopping_notifications_fails(device_cls, stop_error, monkeypatch):
    device = device_cls("AA:BB:CC:DD:EE:FF")
    device.model = "known-model"
    events = []

    class Client:
        is_connected = True

    client = Client()

    @asynccontextmanager
    async def session(*args, **kwargs):
        events.append("enter")
        try:
            yield client
        finally:
            client.is_connected = False
            kwargs["disconnected_callback"](client)
            events.append("exit")

    class ProtocolClient:
        def __init__(self, ble_client):
            self.client = ble_client

        def register_callback(self, *callbacks):
            pass

        async def start_notify(self):
            pass

        async def stop_notify(self):
            raise stop_error

        async def imu_streaming_stop(self):
            pass

    monkeypatch.setattr(parser, "ble_session", session)
    monkeypatch.setattr(parser, "McwClient" if device_cls is McwDevice else "McbClient", ProtocolClient)
    ble_device = type("BleDevice", (), {"address": "AA:BB:CC:DD:EE:FF", "name": "test"})()

    async def connection_lifecycle():
        assert await device.connect(ble_device) is True
        if stop_error is asyncio.CancelledError:
            with pytest.raises(asyncio.CancelledError):
                await device.disconnect()
        else:
            await device.disconnect()

    asyncio.run(connection_lifecycle())

    assert events == ["enter", "exit"]
    assert device._ble_session_stack is None
    assert device.client is None


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


def test_replacing_spell_reset_timer_keeps_new_task_reference():
    device = McwDevice("AA:BB:CC:DD:EE:FF", spell_timeout=3600)

    async def scenario():
        device._schedule_spell_reset()
        old_task = device._spell_reset_timeout_task
        await asyncio.sleep(0)

        device._schedule_spell_reset()
        new_task = device._spell_reset_timeout_task
        assert new_task is not old_task

        await asyncio.sleep(0)
        assert device._spell_reset_timeout_task is new_task

        await device._cancel_background_tasks()

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
