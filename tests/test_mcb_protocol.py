"""Tests for the Magic Caster Box notification protocol."""

import asyncio
from unittest.mock import MagicMock

import pytest

from custom_components.magic_caster_wand.mcw_ble.mcb import (
    CHARGENOTIFY,
    LIDNOTIFY,
    LIDSTATE,
    MESSAGE_TO_RESPONSE_MAP,
    MESSAGEIDS,
    RESPONSEIDS,
    WANDNOTIFY,
    McbClient,
)


@pytest.fixture
def client():
    """An McbClient over a mock transport, with recording callbacks attached."""
    mcb = McbClient(MagicMock())
    mcb.lid_events = []
    mcb.wand_events = []
    mcb.charge_events = []
    mcb.battery_events = []
    mcb.register_callback(
        battery_cb=mcb.battery_events.append,
        lid_cb=mcb.lid_events.append,
        wand_cb=mcb.wand_events.append,
        charge_cb=mcb.charge_events.append,
    )
    return mcb


def test_callbacks_default_to_none_before_registration():
    """A client that never registered callbacks must not raise on a notification."""
    mcb = McbClient(MagicMock())

    assert mcb.callback_battery is None
    assert mcb.callback_lid is None
    assert mcb.callback_wand is None
    assert mcb.callback_charge is None

    # Must be a no-op rather than an AttributeError.
    mcb._handler(None, bytearray([RESPONSEIDS.LID_NOTIFY, 0x00]))
    mcb._handler(None, bytearray([RESPONSEIDS.WAND_NOTIFY, 0x01]))
    mcb._handler(None, bytearray([RESPONSEIDS.CHARGE_NOTIFY, 0x01]))


# ── Combined lid/wand status (0x10) ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("payload", "lid", "wand"),
    [
        (0x00, LIDNOTIFY.LID_ON, WANDNOTIFY.WAND_REMOVED),
        (0x01, LIDNOTIFY.LID_REMOVED, WANDNOTIFY.WAND_REMOVED),
        (0x02, LIDNOTIFY.LID_ON, WANDNOTIFY.WAND_PLUGGED),
        (0x03, LIDNOTIFY.LID_REMOVED, WANDNOTIFY.WAND_PLUGGED),
    ],
)
def test_lid_status_seeds_both_lid_and_wand(client, payload, lid, wand):
    client._handler(None, bytearray([RESPONSEIDS.LID_STATUS, payload]))

    assert client.lid_events == [lid]
    assert client.wand_events == [wand]


def test_lid_status_ignores_unknown_payload(client):
    client._handler(None, bytearray([RESPONSEIDS.LID_STATUS, 0xFF]))

    assert client.lid_events == []
    assert client.wand_events == []


def test_lid_status_ignores_truncated_payload(client):
    client._handler(None, bytearray([RESPONSEIDS.LID_STATUS]))

    assert client.lid_events == []
    assert client.wand_events == []


def test_lid_status_agrees_with_lid_notify(client):
    """The combined status and the notification must decode the lid the same way."""
    client._handler(None, bytearray([RESPONSEIDS.LID_STATUS, 0x00]))
    client._handler(None, bytearray([RESPONSEIDS.LID_NOTIFY, 0x00]))

    assert client.lid_events == [LIDNOTIFY.LID_ON, LIDNOTIFY.LID_ON]


# ── Individual notifications ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("wire", "expected"),
    [(0x00, LIDNOTIFY.LID_ON), (0x01, LIDNOTIFY.LID_REMOVED)],
)
def test_lid_notify_is_active_low(client, wire, expected):
    """The box reports 0 for a seated lid, which is the opposite of the enum value."""
    client._handler(None, bytearray([RESPONSEIDS.LID_NOTIFY, wire]))

    assert client.lid_events == [expected]


@pytest.mark.parametrize(
    ("wire", "expected"),
    [(0x00, WANDNOTIFY.WAND_REMOVED), (0x01, WANDNOTIFY.WAND_PLUGGED)],
)
def test_wand_notify(client, wire, expected):
    client._handler(None, bytearray([RESPONSEIDS.WAND_NOTIFY, wire]))

    assert client.wand_events == [expected]


@pytest.mark.parametrize(
    ("wire", "expected"),
    [(0x00, CHARGENOTIFY.CHARGE_UNPLUGGED), (0x01, CHARGENOTIFY.CHARGE_PLUGGED)],
)
def test_charge_notify(client, wire, expected):
    client._handler(None, bytearray([RESPONSEIDS.CHARGE_NOTIFY, wire]))

    assert client.charge_events == [expected]


def test_battery_notification_is_little_endian(client):
    client._handler_battery(None, bytearray([77]))

    assert client.battery_events == [77]


def test_handler_ignores_empty_frame(client):
    client._handler(None, bytearray())

    assert client.lid_events == []


def test_handler_survives_unknown_opcode(client):
    client._handler(None, bytearray([0xAB, 0x01, 0x02]))

    assert client.lid_events == []


# ── Device information decoding ──────────────────────────────────────────────


def test_paired_wand_address_is_reversed_from_little_endian(client):
    """0x09 reports the address of the wand paired with this box, not the box's own."""
    client._handler(
        None, bytearray([RESPONSEIDS.WAND_ADDRESS, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01])
    )

    assert client._wand_address == "01:02:03:04:05:06"


def test_firmware_version_is_dotted_decimal(client):
    client._handler(None, bytearray([RESPONSEIDS.FIRMWARE_VERSION, 1, 2, 3]))

    assert client._box_firmware_version == "1.2.3"


def test_box_information_decodes_serial_sku_and_device_id(client):
    opcode = RESPONSEIDS.BOX_PRODUCT_INFORMATION

    client._handler(None, bytearray([opcode, 0x01, 0x2A, 0x00, 0x00, 0x00]))
    assert client._box_serial_number == "42"

    client._handler(None, bytearray([opcode, 0x02]) + b"SKU-1\x00")
    assert client._box_sku == "SKU-1"

    client._handler(None, bytearray([opcode, 0x04]) + b"WBMC22G1SHNW\x00")
    assert client._box_device_id == "WBMC22G1SHNW"


@pytest.mark.parametrize(
    ("device_id", "expected"),
    [
        ("WBMC22G1SHNW", "HONOURABLE"),
        ("WBMC22G1SDFW", "DEFIANT"),
        ("WBMC22G1SLYW", "LOYAL"),
        ("WBMC22G1SHRW", "HEROIC"),
        ("WBMC22G1SAVW", "ADVENTUROUS"),
        ("WBMC22G1SWSW", "WISE"),
        ("WBMC22G1SZZW", "UNKNOWN"),
        ("XY", "UNKNOWN"),
        ("", "UNKNOWN"),
    ],
)
def test_device_id_to_type(client, device_id, expected):
    assert client._box_device_id_to_type(device_id) == expected


# ── Outbound commands ────────────────────────────────────────────────────────


def _sent_packets(client):
    """Replace write_command with a recorder and return the recording list."""
    sent = []

    async def record(packet, timeout=5.0):
        sent.append(packet)

    client.write_command = record
    return sent


def test_get_box_serial_number_sends_product_info_read(client):
    """Regression: this used to reference a MESSAGEIDS attribute that did not exist."""
    sent = _sent_packets(client)

    asyncio.run(client.get_box_serial_number())

    assert sent == [bytes([MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ, 0x01])]


def test_get_box_sku_sends_product_info_read(client):
    sent = _sent_packets(client)

    asyncio.run(client.get_box_sku())

    assert sent == [bytes([MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ, 0x02])]


def test_getters_are_cached_after_first_response(client):
    sent = _sent_packets(client)
    client._handler(
        None, bytearray([RESPONSEIDS.BOX_PRODUCT_INFORMATION, 0x01, 0x07, 0, 0, 0])
    )

    assert asyncio.run(client.get_box_serial_number()) == "7"
    assert sent == []


def test_request_lid_status_opcode(client):
    sent = _sent_packets(client)

    asyncio.run(client.request_lid_status())

    assert sent == [bytes([MESSAGEIDS.LID_STATUS_SEND])]


def test_led_off_clears_all(client):
    sent = _sent_packets(client)

    asyncio.run(client.led_off())

    assert sent == [bytes([MESSAGEIDS.LIGHT_CONTROL_CLEAR_ALL])]


def test_opcodes_are_pinned_to_their_wire_values():
    """Constants may be renamed, but the bytes on the wire must not move."""
    assert MESSAGEIDS.FIRMWARE_VERSION_READ == 0x00
    assert MESSAGEIDS.WAND_ADDRESS_READ == 0x09
    assert MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ == 0x0E
    assert MESSAGEIDS.LID_STATUS_SEND == 0x10
    assert MESSAGEIDS.LID_NOTIFY_REQUEST == 0x11
    assert MESSAGEIDS.WAND_NOTIFY_REQUEST == 0x12
    assert MESSAGEIDS.CHARGE_NOTIFY_REQUEST == 0x13
    assert MESSAGEIDS.LIGHT_CONTROL_CLEAR_ALL == 0x40
    assert MESSAGEIDS.LIGHT_CONTROL_SET_LED == 0x42

    assert RESPONSEIDS.WAND_ADDRESS == 0x09
    assert RESPONSEIDS.BOX_PRODUCT_INFORMATION == 0x0E
    assert RESPONSEIDS.LID_STATUS == 0x10


def test_every_request_that_expects_a_reply_is_in_the_response_map():
    """A request missing from the map never waits for its reply, so it silently no-ops."""
    for request in (
        MESSAGEIDS.FIRMWARE_VERSION_READ,
        MESSAGEIDS.WAND_ADDRESS_READ,
        MESSAGEIDS.BOX_PRODUCT_INFORMATION_READ,
        MESSAGEIDS.LID_STATUS_SEND,
        MESSAGEIDS.LID_NOTIFY_REQUEST,
        MESSAGEIDS.WAND_NOTIFY_REQUEST,
        MESSAGEIDS.CHARGE_NOTIFY_REQUEST,
    ):
        assert request in MESSAGE_TO_RESPONSE_MAP


def test_lidstate_covers_every_two_bit_combination():
    assert {s for s in LIDSTATE} == {
        LIDSTATE.LID_ON_NO_WAND,
        LIDSTATE.LID_OFF_NO_WAND,
        LIDSTATE.LID_ON_WAND,
        LIDSTATE.LID_OFF_WAND,
        LIDSTATE.UNKNOWN,
    }
