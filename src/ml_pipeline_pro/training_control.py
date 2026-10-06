"""Cooperative cancellation, ownership fencing, and overall runtime budgets."""

from dataclasses import dataclass, field
from threading import Event
from time import monotonic


class TrainingError(ValueError):
    pass


class TrainingCancelled(TrainingError):
    pass


class TrainingBudgetExceeded(TrainingError):
    pass


class OwnershipLost(Exception):
    pass


@dataclass
class TrainingControl:
    deadline: float | None = None
    cancelled: Event = field(default_factory=Event)
    ownership_lost: Event = field(default_factory=Event)

    def check(self) -> None:
        if self.ownership_lost.is_set():
            raise OwnershipLost("The tuning worker no longer owns this job")
        if self.cancelled.is_set():
            raise TrainingCancelled("Training was cancelled by the tuning job")
        if self.deadline is not None and monotonic() >= self.deadline:
            raise TrainingBudgetExceeded("The overall tuning runtime budget was exhausted")
