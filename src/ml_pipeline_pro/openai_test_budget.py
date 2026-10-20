"""Persistent, conservative reservations for the single authorized $2 test run.

This is a testing control, not an account-wide application spending limit.
Uncertain or completed requests keep their entire reservation; no refunds are
needed to stay within the authorization. One process holds the runner lock.
"""

import json
import os
from datetime import UTC, date, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from filelock import FileLock, Timeout

from ml_pipeline_pro.conversation_model import ConversationModelError

MODEL = "gpt-5.4-mini"
PRICING_DATE = "2026-10-20"
INPUT_RATE = Decimal("0.75") / 1_000_000
OUTPUT_RATE = Decimal("4.50") / 1_000_000
RESERVATION_LIMIT = Decimal("1.90")
PRICING_URL = "https://developers.openai.com/api/docs/models/gpt-5.4-mini"


def _stop():
    return ConversationModelError("chat_limit_exceeded", "Live testing budget admission refused")


class OpenAITestBudget:
    """Durably reserve before sending; refuse simultaneous runners and stale pricing."""

    def __init__(self, path: Path, *, model=MODEL, today=None):
        if model != MODEL or (today or datetime.now(UTC).date()) != date.fromisoformat(
            PRICING_DATE
        ):
            raise _stop()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + ".lock", timeout=0)
        self._held = False
        self.state = None

    def __enter__(self):
        try:
            self.lock.acquire()
        except Timeout:
            raise _stop() from None
        self._held = True
        try:
            if self.path.exists():
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
                expected = self._empty()
                if set(self.state) != set(expected) or any(
                    self.state[key] != expected[key] for key in expected if key != "reservations"
                ):
                    raise _stop()
                entries = self.state["reservations"]
                if (
                    not isinstance(entries, list)
                    or any(
                        not isinstance(item, dict)
                        or set(item) != {"kind", "input", "output", "usd"}
                        or item["kind"] not in {"count", "generation"}
                        or self._cost(item["input"], item["output"]) != Decimal(item["usd"])
                        for item in entries
                    )
                    or self.reserved > RESERVATION_LIMIT
                ):
                    raise _stop()
            else:
                self.state = self._empty()
                self._save()
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self._held:
            self._held = False
            self.lock.release()

    @staticmethod
    def _empty():
        return {
            "version": 1,
            "model": MODEL,
            "pricing_date": PRICING_DATE,
            "pricing_source": PRICING_URL,
            "input_per_million_usd": "0.75",
            "output_per_million_usd": "4.50",
            "authorization_usd": "2.00",
            "reservation_limit_usd": "1.90",
            "reservations": [],
        }

    @staticmethod
    def _cost(input_tokens, output_tokens):
        if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
            raise _stop()
        return (input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE).quantize(
            Decimal("0.000001"), rounding=ROUND_CEILING
        )

    @property
    def reserved(self):
        return sum((Decimal(item["usd"]) for item in self.state["reservations"]), Decimal(0))

    def _save(self):
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(self.state, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.path)

    def _reserve(self, kind, input_tokens, output_tokens):
        if not self._held:
            raise _stop()
        cost = self._cost(input_tokens, output_tokens)
        if self.reserved + cost > RESERVATION_LIMIT:
            raise _stop()
        self.state["reservations"].append(
            {"kind": kind, "input": input_tokens, "output": output_tokens, "usd": str(cost)}
        )
        # Any persistence failure aborts before the network request, never after it.
        self._save()

    def reserve_count(self, input_byte_bound):
        # Text-only requests: reserve every serialized UTF-8 byte as an input token
        # plus 1024 framing tokens. Charge at the full input rate even if counting
        # is free. No generated output or hosted tool is requested by this endpoint.
        self._reserve("count", input_byte_bound + 1024, 0)

    def reserve_generation(self, input_tokens, output_tokens):
        self._reserve("generation", input_tokens, output_tokens)
