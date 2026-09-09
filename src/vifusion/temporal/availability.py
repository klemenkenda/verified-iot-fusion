"""Availability models.

Section 5.1: if a dataset has no recorded availability, the adapter **must** label the
availability model as simulated and store its parameters. Section 14 lists ambiguous
availability times as a risk whose consequence is leakage or overstated realism, and the
mitigation is to classify every timing field rather than to guess well.

Phase 2 implements the two models the roadmap asks for — recorded and simulated. Bounded
and inferred belong to Phase 5, where real dissemination windows are reconstructed for
USCRN, and they raise here rather than silently degrading to a guess.

Every model reports :attr:`AvailabilityModel.parameters`, which the adapter stores in the
run manifest's ``availability_parameters``. A simulated model whose parameters are not
recorded is indistinguishable in the results from a recorded one, which is precisely the
overstatement the plan warns about.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from vifusion.config import AvailabilityModel as AvailabilityModelName


class AvailabilityModel(ABC):
    """Derives an ``available_time`` for a record whose event time is known."""

    name: AvailabilityModelName

    @abstractmethod
    def available_time(self, event_time: datetime, recorded: datetime | None) -> datetime:
        """Return the earliest defensible time the record could have been used."""

    @property
    def parameters(self) -> dict[str, Any]:
        """Parameters to record in the manifest alongside the model name."""
        return {}


class RecordedAvailability(AvailabilityModel):
    """Availability read directly from the source.

    Used where the dataset states when a record became usable — Enefit's ``data_block_id``,
    or a dissemination timestamp in a delivered file.
    """

    name: AvailabilityModelName = "recorded"

    def available_time(self, event_time: datetime, recorded: datetime | None) -> datetime:
        if recorded is None:
            raise ValueError(
                "recorded availability model requires an availability time from the source; "
                "use SimulatedAvailability and declare its parameters instead of assuming one"
            )
        if recorded < event_time:
            raise ValueError(
                f"recorded availability {recorded.isoformat()} precedes the event at "
                f"{event_time.isoformat()}"
            )
        return recorded


class SimulatedAvailability(AvailabilityModel):
    """Availability assumed to lag the event by a fixed delay.

    The delay is a declared experimental parameter, not a detail: section 14 requires
    simulated arrivals to be labelled explicitly, and the sensitivity of results to this
    value is a required Phase 10 analysis.
    """

    name: AvailabilityModelName = "simulated"

    def __init__(self, delay: timedelta) -> None:
        if delay < timedelta(0):
            raise ValueError("simulated availability delay cannot be negative")
        self.delay = delay

    def available_time(self, event_time: datetime, recorded: datetime | None) -> datetime:
        return event_time + self.delay

    @property
    def parameters(self) -> dict[str, Any]:
        return {"delay_seconds": self.delay.total_seconds()}


def unsupported(name: AvailabilityModelName) -> AvailabilityModel:
    """Availability models deferred to Phase 5.

    ``bounded`` and ``inferred`` require reconstructing dissemination windows from real
    publication behaviour, which is Phase 5 work against USCRN. They raise rather than
    approximating, because an availability model that quietly guesses is the failure this
    module exists to prevent.
    """
    raise NotImplementedError(
        f"availability model {name!r} is implemented in Phase 5 against real dissemination "
        "windows; Phase 2 supports 'recorded' and 'simulated'"
    )
