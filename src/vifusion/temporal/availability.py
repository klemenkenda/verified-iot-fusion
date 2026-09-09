"""Availability models.

Section 5.1: if a dataset has no recorded availability, the adapter **must** label the
availability model as simulated and store its parameters. Section 14 lists ambiguous
availability times as a risk whose consequence is leakage or overstated realism, and the
mitigation is to classify every timing field rather than to guess well.

Three of the four models section 12 names are implemented, and each has a dataset that uses
it: ``recorded`` for Enefit, whose ``data_block_id`` states which records were delivered
together; ``bounded`` for USCRN, whose availability must be reconstructed as an upper bound
from the dissemination window of the update file a record arrived in; ``simulated`` for
Beijing, which records no availability at all, and for USCRN's quality-controlled final
products. ``inferred`` — availability estimated from an observed publication-lag
distribution — has no consumer among the three committed datasets of section 8.6 and is
therefore *not* implemented: it raises. Writing it now would add a model that nothing routes
through, which is the defect this module was audited for in the first place.

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


class BoundedAvailability(AvailabilityModel):
    """Availability known only as an upper bound: the close of a dissemination window.

    USCRN publishes hourly update files, and the file a record appears in states the window
    during which it was disseminated. The record became usable at *some* instant inside that
    window; the only defensible choice is its close, because any earlier instant claims a
    delivery the archive does not evidence. Taking the close is conservative in the direction
    that matters — it can only make a record eligible later than it truly was, never earlier,
    so it cannot manufacture a leak. Section 8.2 calls this reconstructing an availability
    upper bound, and it is the harder adapter problem the build order puts first.

    The window close is supplied per record by the adapter, because only the adapter knows
    which file the record arrived in. ``window`` names the containing window in the
    parameters so that the derivation stays auditable after normalisation.
    """

    name: AvailabilityModelName = "bounded"

    def __init__(self, window_description: str) -> None:
        self.window_description = window_description

    def available_time(self, event_time: datetime, recorded: datetime | None) -> datetime:
        if recorded is None:
            raise ValueError(
                "bounded availability requires the close of the window the record was "
                "disseminated in; without it there is no bound, only a guess"
            )
        if recorded < event_time:
            raise ValueError(
                f"dissemination window closes at {recorded.isoformat()}, before the "
                f"observation at {event_time.isoformat()}; a record cannot be delivered "
                "before it was measured, so either the window or the timestamp is misparsed"
            )
        return recorded

    @property
    def parameters(self) -> dict[str, Any]:
        return {"window": self.window_description}


def unsupported(name: AvailabilityModelName) -> AvailabilityModel:
    """The availability model with no consumer: ``inferred``.

    Inferring availability from an observed publication-lag distribution is a real model and
    a defensible one, but none of the three datasets section 8.6 commits to needs it — Enefit
    records its delivery blocks, USCRN bounds them, Beijing records nothing and is therefore
    simulated. Implementing it anyway would produce a model that nothing imports and no test
    exercises, which is exactly what the Phase 2 audit found and reopened.

    It raises rather than approximating, because an availability model that quietly guesses
    is the failure this module exists to prevent.
    """
    raise NotImplementedError(
        f"availability model {name!r} has no implementation: no committed dataset requires "
        "it. Use 'recorded', 'bounded', or 'simulated', or implement it here together with "
        "the adapter that needs it"
    )
