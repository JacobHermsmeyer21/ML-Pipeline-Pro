"""Explicit evaluation/deployment timing profiles and payload-free boundary logs."""

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic

DIAGNOSTIC_PROFILE = "laptop-unbounded-diagnostic"
PROFILE_NAMES = ("default", "laptop-five-minute", DIAGNOSTIC_PROFILE)


@dataclass(frozen=True)
class TimingProfile:
    name: str
    model_seconds: int | None
    turn_seconds: int | None
    client_seconds: int | None
    dialogue_suite_seconds: int | None
    snippet_suite_seconds: int | None

    def settings_overrides(self):
        if self.name == "default":
            return {}
        overrides = {
            "chat_model_timeout_seconds": self.model_seconds,
            "chat_timeout_seconds": self.turn_seconds,
        }
        if self.name == DIAGNOSTIC_PROFILE:
            overrides["chat_unbounded_diagnostic"] = True
        return overrides


def timing_profile(name: str) -> TimingProfile:
    if name == "default":
        return TimingProfile(name, 20, 60, 90, 600, 120)
    if name == "laptop-five-minute":
        return TimingProfile(name, 240, 270, 300, 3300, 2400)
    if name == DIAGNOSTIC_PROFILE:
        return TimingProfile(name, None, None, None, None, None)
    raise ValueError("Unknown timing profile")


@contextmanager
def timed_boundary(phase: str, correlation_id: str | None = None):
    """Log elapsed time without prompts, credentials, record IDs or exception text."""
    logger = logging.getLogger(__name__)
    started = monotonic()
    extra = {"correlation_id": correlation_id} if correlation_id else {}
    logger.info("ai_boundary phase=%s event=start", phase, extra=extra)
    outcome = "completed"
    try:
        yield
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except BaseException:
        outcome = "failed"
        raise
    finally:
        logger.info(
            "ai_boundary phase=%s event=end outcome=%s",
            phase,
            outcome,
            extra={**extra, "duration_ms": round((monotonic() - started) * 1000, 3)},
        )
