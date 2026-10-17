"""Sensitive BLE and HTTP transport data must not enter diagnostic logs."""

import logging
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.magic_caster_wand.mcb_ble.mcb import McbClient
from custom_components.magic_caster_wand.mcw_ble.mcw import McwClient
from custom_components.magic_caster_wand.mcw_ble.remote_tensor_spell_detector import RemoteTensorSpellDetector

SECRET = "token=private AA:BB:CC:DD:EE:FF https://user:password@192.0.2.4"


@pytest.mark.parametrize("client_type", [McwClient, McbClient])
def test_protocol_logs_exclude_raw_packets(caplog, client_type):
    caplog.set_level(logging.DEBUG, logger="custom_components.magic_caster_wand")
    packet = bytearray(b"\xff" + SECRET.encode())
    client_type(Mock())._handler(None, packet)
    assert SECRET not in caplog.text
    assert packet.hex() not in caplog.text


async def test_remote_logs_exclude_url_payload_body_and_exceptions(caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.magic_caster_wand")
    response = Mock()
    response.raise_for_status = Mock()
    response.json = AsyncMock(return_value={"outputs": [{"data": SECRET}]})
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = Mock()
    session.get.side_effect = RuntimeError(SECRET)
    session.post.return_value = context
    detector = RemoteTensorSpellDetector("test", "https://user:password@192.0.2.4", session=session)
    assert not await detector.check_connectivity()
    await detector._initialize_model()
    await detector._invoke({"input": SECRET})
    session.post.side_effect = RuntimeError(SECRET)
    assert await detector._invoke({"input": SECRET}) is None
    assert SECRET not in caplog.text
    assert "user:password" not in caplog.text
    assert "192.0.2.4" not in caplog.text
    assert "private" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_malformed_macros_do_not_log_raw_user_values(caplog):
    from custom_components.magic_caster_wand.common_ble.common import build_macro

    caplog.set_level(logging.DEBUG, logger="custom_components.magic_caster_wand")
    build_macro([{SECRET: SECRET}, {"buzz": SECRET}, [SECRET]])
    assert SECRET not in caplog.text
    assert "Skipping" in caplog.text
