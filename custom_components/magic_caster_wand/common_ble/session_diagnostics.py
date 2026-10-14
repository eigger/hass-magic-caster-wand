"""Build and retain structured reports for BLE sessions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from blesession import SessionDropped, SessionReports, SessionTrace, build_report, stages
from blesession.hass import radio_facts

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

T = TypeVar("T")


STAGE_MAP = {
    "subscribe": stages.SESSION,
    "initialize": stages.AUTH,
    "notification": stages.SESSION,
    "transfer": stages.TRANSFER,
}


class BLESessionDiagnostics:
    """Keep the latest BLE operation and failure reports for one device."""

    def __init__(self, address: str, noun: str) -> None:
        """Initialize diagnostics before Home Assistant setup is complete."""
        self.address = address
        self.noun = noun
        self.hass: HomeAssistant | None = None
        self.reports = SessionReports()

    def bind_hass(self, hass: HomeAssistant) -> None:
        """Enable radio facts once the device is loaded by Home Assistant."""
        self.hass = hass

    def new_trace(self) -> SessionTrace:
        """Create a trace with wand/box stages mapped to shared BLE stages."""
        return SessionTrace(stage_map=STAGE_MAP)

    def record(self, operation: str, trace: SessionTrace, exc: BaseException | None = None) -> dict[str, Any] | None:
        """Build and retain one report, ignoring expected task cancellation."""
        if isinstance(exc, asyncio.CancelledError):
            return None

        facts = radio_facts(self.hass, self.address, trace.link) if self.hass is not None else {}
        report = build_report(
            operation=operation,
            trace=trace,
            exc=exc,
            facts=facts,
            noun=self.noun,
        )
        return self.reports.record(report)

    def record_failure(self, operation: str, stage: str, exc: BaseException) -> dict[str, Any] | None:
        """Record an error raised outside an active session trace."""
        trace = self.new_trace()
        trace.fail(stage)
        return self.record(operation, trace, exc)

    async def run_operation(
        self,
        operation: str,
        action: Callable[[], Awaitable[T]],
        *,
        connected: bool,
    ) -> T | None:
        """Run and report one user-requested BLE operation."""
        trace = self.new_trace()
        if not connected:
            exc = SessionDropped(f"Cannot run {operation}: device is not connected")
            trace.fail("session")
            self.record(operation, trace, exc)
            return None

        try:
            with trace.timed("transfer"):
                result = await action()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.record(operation, trace, err)
            raise
        self.record(operation, trace)
        return result
