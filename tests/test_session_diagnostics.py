"""Tests for retained blesession diagnostic reports."""

import asyncio

from blesession import SessionDropped

from custom_components.magic_caster_wand.common_ble.session_diagnostics import BLESessionDiagnostics
from custom_components.magic_caster_wand.mcw_ble.mcw import McwClient
from custom_components.magic_caster_wand.mcw_ble.mcw_device import McwDevice


def test_success_report_keeps_latest_failure_and_counts_failures():
    diagnostics = BLESessionDiagnostics("AA:BB:CC:DD:EE:FF", "wand")
    notifications = []
    diagnostics.reports.add_listener(lambda: notifications.append(diagnostics.reports.last))

    diagnostics.record_failure("connect", "session", SessionDropped("link lost"))
    failed_report = diagnostics.reports.last_failure
    diagnostics.record("connect", diagnostics.new_trace())

    assert diagnostics.reports.failures == 1
    assert diagnostics.reports.last_failure is failed_report
    assert diagnostics.reports.last["success"] is True
    assert notifications == [failed_report, diagnostics.reports.last]


def test_cancelled_operation_is_not_recorded():
    diagnostics = BLESessionDiagnostics("AA:BB:CC:DD:EE:FF", "wand")

    async def action():
        raise asyncio.CancelledError

    try:
        asyncio.run(diagnostics.run_operation("send_macro", action, connected=True))
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("operation cancellation should propagate")

    assert diagnostics.reports.last is None
    assert diagnostics.reports.failures == 0


def test_swallowed_notification_parser_error_is_reported():
    client = McwClient(object())
    errors = []
    client.register_error_callback(errors.append)
    client.register_callback(
        lambda _spell: (_ for _ in ()).throw(ValueError("callback failed")),
        lambda _battery: None,
        lambda _buttons: None,
        lambda _calibration: None,
        lambda _imu: None,
    )

    client._parse_spell(bytearray([0x24, 0, 0, 3, *b"abc"]))

    assert len(errors) == 1
    assert str(errors[0]) == "callback failed"


def test_disconnect_during_connect_setup_is_not_double_counted():
    device = McwDevice("AA:BB:CC:DD:EE:FF")
    client = object()
    device.client = client
    device._connecting = True

    device._on_disconnect(client)
    assert device.diagnostics.reports.failures == 0

    device.diagnostics.record_failure("connect", "initialize", RuntimeError("setup failed"))
    assert device.diagnostics.reports.failures == 1
