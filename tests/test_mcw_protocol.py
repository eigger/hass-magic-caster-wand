"""Tests for the Magic Caster Wand command response protocol."""

from unittest.mock import MagicMock

from custom_components.magic_caster_wand.mcw_ble.mcw import RESPONSEIDS, McwClient


def test_product_information_waiter_requires_the_requested_subtype():
    client = McwClient(MagicMock())
    client._waiting_for_msg_id = RESPONSEIDS.WAND_PRODUCT_INFORMATION
    client._waiting_for_info_type = 0x04

    assert client._response_matches_waiter(bytearray([0x0E, 0x02, 0x41])) is False
    assert client._response_matches_waiter(bytearray([0x0E, 0x04, 0x41])) is True


def test_malformed_response_does_not_complete_waiter():
    client = McwClient(MagicMock())
    client._waiting_for_msg_id = RESPONSEIDS.CHALLENGE

    client._handler(None, bytearray([RESPONSEIDS.CHALLENGE, 0x01]))

    assert not client._waiting_cmd_event.is_set()
    assert client._waiting_for_msg_id == RESPONSEIDS.CHALLENGE
