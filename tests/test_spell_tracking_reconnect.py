"""Spell tracking across a reconnect.

IMU streaming is firmware state that dies with the connection, while the detector
session that gates the button and IMU callbacks outlives it. These tests pin the
two together: a reconnect must re-arm streaming when tracking was on, must not
when it was off, and must not claim to be tracking when re-arming failed.

They also cover the ordering hazard on a quick reconnect: bleak dispatches the
disconnect callback through the event loop, so the old link's callback can arrive
after a new connection is already up, and must not tear it down.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from custom_components.magic_caster_wand.mcw_ble import parser
from custom_components.magic_caster_wand.mcw_ble.parser import McbDevice, McwDevice


class FakeClient:
    """Minimal stand-in for the connected BleakClient."""

    is_connected = True


class FakeBleDevice:
    """Minimal stand-in for the BLEDevice handed to connect()."""

    name = "MCW-7E2939D2"
    address = "AA:BB:CC:DD:EE:FF"


class FakeSession:
    """Stand-in for the detector's aiohttp session.

    ``is_active`` is ``session is not None and not session.closed``, so an open
    session is what represents "the user switched spell tracking on".
    """

    closed = False


class FakeMcwClient:
    """Records the streaming commands the device sends to the wand."""

    def __init__(self, start_error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._start_error = start_error

    async def imu_streaming_start(self) -> None:
        self.calls.append("start")
        if self._start_error is not None:
            raise self._start_error

    async def imu_streaming_stop(self) -> None:
        self.calls.append("stop")

    # -- used only when driving the real connect() --

    def register_callback(self, *callbacks) -> None:
        pass

    async def start_notify(self) -> None:
        self.calls.append("start_notify")

    async def stop_notify(self) -> None:
        self.calls.append("stop_notify")


def make_device(tracking_wanted: bool, start_error: Exception | None = None) -> McwDevice:
    """A connected wand whose tracker session reflects the user's intent.

    ``is_active`` on the detector is what survives a disconnect, so setting it is
    how a test says "the user had spell tracking switched on".
    """
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    device.client = FakeClient()
    device._mcw = FakeMcwClient(start_error)
    device._spell_tracker._detector._session = FakeSession() if tracking_wanted else None
    return device


def press_all_buttons(device: McwDevice, pressed: bool = True) -> None:
    """Deliver a button notification inside a running loop.

    The callback spawns the casting-LED write as a task, which needs a loop even
    though the write itself goes to the fake client.
    """

    async def scenario():
        device._callback_buttons({"button_all": pressed})
        await asyncio.sleep(0)  # let the spawned LED task run

    asyncio.run(scenario())


def feed_imu(device: McwDevice, count: int) -> None:
    """Deliver ``count`` identical IMU samples."""
    sample = {"accel_x": 0.1, "accel_y": 0.2, "accel_z": 0.9, "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0}
    device._callback_imu([sample] * count)


def test_tracking_intent_reflects_the_detector_session():
    """The fixture only means something if intent is wired to the session."""
    assert make_device(tracking_wanted=True).spell_tracking_wanted is True
    assert make_device(tracking_wanted=False).spell_tracking_wanted is False


# ── Resuming on reconnect ────────────────────────────────────────────────────


def test_reconnect_resumes_streaming_when_tracking_was_on():
    device = make_device(tracking_wanted=True)

    asyncio.run(device._resume_imu_streaming())

    assert device._mcw.calls == ["start"], "streaming must be re-armed after a reconnect"
    assert device.spell_tracking_active is True


def test_each_resume_issues_a_single_start():
    """One start per call, never a burst.

    Re-arming is driven by connect(), which returns early for an already-open
    connection, so the helper is reached once per actual reconnect. What it must
    guarantee is that a call does not issue the command more than once.
    """
    device = make_device(tracking_wanted=True)

    asyncio.run(device._resume_imu_streaming())
    assert device._mcw.calls == ["start"]

    asyncio.run(device._resume_imu_streaming())
    assert device._mcw.calls == ["start", "start"], "a second reconnect re-arms once more"


def test_reconnect_does_not_resume_when_tracking_was_off():
    device = make_device(tracking_wanted=False)

    asyncio.run(device._resume_imu_streaming())

    assert device._mcw.calls == [], "streaming must stay off if the user never turned it on"
    assert device.spell_tracking_active is False


def connect_device(device: McwDevice, monkeypatch, start_error: Exception | None = None) -> bool:
    """Drive the real connect() with the BLE layer stubbed out.

    Patches the two things connect() reaches for -- the transport and the protocol
    client -- so the rest of the method, including the resume step, runs as written.
    """
    fake_client = FakeMcwClient(start_error)

    async def fake_establish(cls, ble_device, address, disconnected_callback=None):
        return FakeClient()

    monkeypatch.setattr(parser, "establish_connection", fake_establish)
    monkeypatch.setattr(parser, "McwClient", lambda client: fake_client)
    # The model probe talks to the wand; it is not what these tests are about.
    device.model = "WBMC22G1SHNW"

    return asyncio.run(device.connect(FakeBleDevice()))


def test_connect_resumes_streaming_when_tracking_was_on(monkeypatch):
    """The end-to-end wiring: reconnecting a wand that was tracking re-arms the
    stream without the user touching the Spell Tracking switch."""
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    device._spell_tracker._detector._session = FakeSession()

    assert connect_device(device, monkeypatch) is True

    assert device._mcw.calls == ["start_notify", "start"], "connect() must re-arm IMU streaming"
    assert device.spell_tracking_active is True


def test_connect_does_not_resume_when_tracking_was_off(monkeypatch):
    device = McwDevice("AA:BB:CC:DD:EE:FF")

    assert connect_device(device, monkeypatch) is True

    assert device._mcw.calls == ["start_notify"], "a wand that was not tracking must stay idle"
    assert device.spell_tracking_active is False


def test_connect_succeeds_even_if_the_resume_fails(monkeypatch):
    """A wand that is connected but not streaming still beats no wand at all, so
    the failure must not take the connection down with it."""
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    device._spell_tracker._detector._session = FakeSession()

    assert connect_device(device, monkeypatch, start_error=RuntimeError("write failed")) is True

    assert device.spell_tracking_wanted is True
    assert device.spell_tracking_active is False, "a failed resume must not report as tracking"


# ── A failed resume must not look like success ───────────────────────────────


def test_failed_resume_is_not_reported_as_tracking():
    """Logging and carrying on would recreate the bug: the switch would read on
    while no IMU samples arrive."""
    device = make_device(tracking_wanted=True, start_error=RuntimeError("write failed"))

    asyncio.run(device._resume_imu_streaming())

    assert device._mcw.calls == ["start"], "the attempt is still made"
    assert device.spell_tracking_wanted is True, "the user's intent is unchanged"
    assert device.spell_tracking_active is False, "but tracking must not claim to be running"


def test_failed_resume_does_not_break_the_connection():
    """A wand that is connected but not streaming still beats no wand at all."""
    device = make_device(tracking_wanted=True, start_error=RuntimeError("write failed"))

    asyncio.run(device._resume_imu_streaming())  # must not raise


def test_failed_resume_is_logged(caplog):
    device = make_device(tracking_wanted=True, start_error=RuntimeError("write failed"))

    with caplog.at_level("WARNING"):
        asyncio.run(device._resume_imu_streaming())

    assert "Failed to resume IMU streaming" in caplog.text


def test_callbacks_stay_inert_while_streaming_is_down():
    """With no samples arriving a cast can only fail, so it must not start."""
    device = make_device(tracking_wanted=True, start_error=RuntimeError("write failed"))
    asyncio.run(device._resume_imu_streaming())

    press_all_buttons(device)

    assert device._button_all_pressed is False, "no cast may start without IMU data"


# ── Interrupted casts do not survive a reconnect ─────────────────────────────


def test_disconnect_clears_an_interrupted_cast():
    """Mid-cast the recording is open and button_all is latched. The wand reports
    buttons released while disconnected, so a stale latch means the next press is
    not seen as a transition and no cast ever starts."""
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())

    press_all_buttons(device)
    assert device._button_all_pressed is True
    assert device._spell_tracker._state.tracking_active == 1

    device._on_disconnect(device.client)

    assert device._button_all_pressed is False, "a latched press must not survive a reconnect"
    assert device._spell_tracker._state.tracking_active == 0, "the recording must be closed"
    assert device._imu_streaming is False, "streaming is gone with the connection"


def test_explicit_disconnect_clears_an_interrupted_cast():
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())
    press_all_buttons(device)

    asyncio.run(device.disconnect())

    assert device._button_all_pressed is False
    assert device._spell_tracker._state.tracking_active == 0


def test_disconnect_clears_the_cast_even_without_a_client():
    """disconnect() skips its body when the link is already gone, but the cast
    state still has to be dropped."""
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())
    press_all_buttons(device)
    device.client = None

    asyncio.run(device.disconnect())

    assert device._button_all_pressed is False
    assert device._imu_streaming is False


def test_samples_do_not_bleed_into_the_next_cast():
    """The positions recorded before a disconnect must not be prepended to the
    cast that follows it."""
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())
    press_all_buttons(device)

    feed_imu(device, 5)
    assert device._spell_tracker._state.position_count > 1

    device._on_disconnect(device.client)

    assert device._spell_tracker._state.position_count == 0, "the interrupted run must be discarded"


def test_a_cast_works_normally_after_reconnecting():
    """The whole point: press-release must be seen as a transition again without
    the user touching the Spell Tracking switch."""
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())
    press_all_buttons(device)
    device._on_disconnect(device.client)

    # Reconnect: a fresh client, and the resume step connect() performs.
    device.client = FakeClient()
    device._mcw = FakeMcwClient()
    asyncio.run(device._resume_imu_streaming())

    assert device.spell_tracking_active is True

    press_all_buttons(device)

    assert device._button_all_pressed is True, "the press must register as a new cast"
    assert device._spell_tracker._state.tracking_active == 1


# ── A late disconnect callback must not tear down the new connection ─────────


def test_superseded_disconnect_callback_is_ignored():
    """bleak dispatches the disconnect callback through the event loop, so a quick
    reconnect can install a new client before the old link's callback runs. Acting
    on it then would clear the state of the connection that replaced it."""
    device = make_device(tracking_wanted=True)
    old_client = device.client
    asyncio.run(device._resume_imu_streaming())

    # Reconnect lands first: new client, new protocol client, streaming re-armed.
    device.client = FakeClient()
    device._mcw = FakeMcwClient()
    asyncio.run(device._resume_imu_streaming())

    device._on_disconnect(old_client)  # the old link's callback, arriving late

    assert device.client is not None, "the live connection must survive"
    assert device._mcw is not None, "clearing this would break buzz, LEDs and macros"
    assert device.spell_tracking_active is True, "streaming is armed on the new link"


def test_superseded_disconnect_callback_does_not_report_offline():
    """The connection coordinator drives entity availability, so a stale False
    would mark a live wand unavailable."""
    device = make_device(tracking_wanted=True)
    old_client = device.client
    coordinator = MagicMock()
    device._coordinator_connection = coordinator
    device.client = FakeClient()

    device._on_disconnect(old_client)

    coordinator.async_set_updated_data.assert_not_called()


def test_superseded_disconnect_callback_does_not_abort_a_live_cast():
    """A cast in flight on the new connection must not be discarded by the old
    connection's callback."""
    device = make_device(tracking_wanted=True)
    old_client = device.client
    device.client = FakeClient()
    device._mcw = FakeMcwClient()
    asyncio.run(device._resume_imu_streaming())
    press_all_buttons(device)
    feed_imu(device, 5)

    device._on_disconnect(old_client)

    assert device._button_all_pressed is True, "the press is still held on the live link"
    assert device._spell_tracker._state.tracking_active == 1, "the recording must stay open"
    assert device._spell_tracker._state.position_count > 1, "samples must not be discarded"


def test_disconnect_callback_for_the_current_client_still_applies():
    """The guard must not swallow the real thing."""
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())

    device._on_disconnect(device.client)

    assert device.client is None
    assert device._mcw is None
    assert device._imu_streaming is False


def test_disconnect_callback_after_an_explicit_disconnect_is_ignored():
    """disconnect() clears the client, so the callback it triggers arrives with
    self.client already None and must not be mistaken for a live connection."""
    device = make_device(tracking_wanted=True)
    old_client = device.client
    coordinator = MagicMock()
    asyncio.run(device.disconnect())
    device._coordinator_connection = coordinator
    device.client = FakeClient()  # a reconnect that beat the callback
    device._mcw = FakeMcwClient()

    device._on_disconnect(old_client)

    assert device.client is not None
    coordinator.async_set_updated_data.assert_not_called()


def test_box_ignores_a_superseded_disconnect_callback():
    """McbDevice has the identical shape and the identical exposure."""
    device = McbDevice("AA:BB:CC:DD:EE:FF")
    old_client = FakeClient()
    device.client = old_client
    device._mcb = object()

    device.client = FakeClient()  # reconnected before the callback ran
    device._on_disconnect(old_client)

    assert device.client is not None
    assert device._mcb is not None


def test_box_disconnect_callback_for_the_current_client_still_applies():
    device = McbDevice("AA:BB:CC:DD:EE:FF")
    device.client = FakeClient()
    device._mcb = object()

    device._on_disconnect(device.client)

    assert device.client is None
    assert device._mcb is None


# ── Streaming state tracks the explicit start/stop calls ─────────────────────


def test_streaming_state_follows_start_and_stop():
    device = make_device(tracking_wanted=True)

    asyncio.run(device.imu_streaming_start())
    assert device.spell_tracking_active is True

    asyncio.run(device.imu_streaming_stop())
    assert device.spell_tracking_active is False
    assert device.spell_tracking_wanted is True, "stopping the stream is not withdrawing intent"


def test_stopping_streaming_while_disconnected_still_clears_the_flag():
    device = make_device(tracking_wanted=True)
    asyncio.run(device._resume_imu_streaming())
    device.client = None

    asyncio.run(device.imu_streaming_stop())

    assert device.spell_tracking_active is False


@pytest.mark.parametrize("wanted", [True, False])
def test_detection_mode_reports_server_only_when_intended(wanted):
    """The mode sensor follows intent, not the momentary streaming state."""
    device = make_device(tracking_wanted=wanted)

    assert device.spell_detection_mode == ("Server" if wanted else "Wand")
