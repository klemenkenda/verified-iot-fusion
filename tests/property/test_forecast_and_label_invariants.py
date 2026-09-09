"""Property-based invariants for revisable forecasts and delayed labels.

The named scenarios cover these by hand; this generates them. Forecast revision is where a
leak is most tempting — a later issue is genuinely better information — and label reveal is
where one is easiest to introduce accidentally, by scoring against an outcome the system
could not yet have known.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vifusion.temporal import oracle
from vifusion.temporal.boundaries import is_label_usable, is_visible
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import ForecastValue

BASE = datetime(2024, 1, 1, tzinfo=UTC)
HOUR = timedelta(hours=1)
LEAD = 3 * HOUR

FORECAST = ForecastValue(
    name="fc",
    entity_id="e1",
    source_id="nwp",
    feature_name="temp_fc",
    lead=LEAD,
)

SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@st.composite
def _forecast_log(draw: st.DrawFn) -> list[CanonicalRecord]:
    """Several issues per valid time, each with an independent publication lag.

    The lag matters: section 14 lists "forecast issue time differs from publication time" as
    a risk in its own right, so issue order and availability order are generated separately
    and routinely disagree.
    """
    records: list[CanonicalRecord] = []
    for index in range(draw(st.integers(min_value=0, max_value=10))):
        issue_hour = draw(st.integers(min_value=0, max_value=8))
        publication_lag = draw(st.integers(min_value=0, max_value=4))
        valid_hour = draw(st.integers(min_value=0, max_value=12))
        issued = BASE + issue_hour * HOUR
        records.append(
            CanonicalRecord(
                record_id=f"f{index:03d}",
                kind=RecordKind.FORECAST,
                entity_id="e1",
                source_id="nwp",
                feature_name="temp_fc",
                value=float(draw(st.integers(min_value=-50, max_value=50))),
                event_time=issued,
                issued_time=issued,
                available_time=issued + publication_lag * HOUR,
                valid_time=BASE + valid_hour * HOUR,
                revision_id=f"r{index:03d}",
            )
        )
    return records


_TIMES = st.lists(
    st.integers(min_value=0, max_value=9).map(lambda hour: BASE + hour * HOUR),
    min_size=1,
    max_size=4,
    unique=True,
).map(sorted)


@given(log=_forecast_log(), times=_TIMES)
@SETTINGS
def test_engine_and_oracle_select_the_same_issue(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    requests = [PredictionRequest("e1", moment) for moment in times]
    for vector in replay(log, requests, [FORECAST]).vectors:
        expected = oracle.evaluate(log, FORECAST, vector.prediction_time)
        actual = vector.by_name("fc")
        assert actual.value == expected.value
        assert actual.lineage == expected.lineage


@given(log=_forecast_log(), times=_TIMES)
@SETTINGS
def test_the_selected_issue_is_the_latest_eligible_one(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Stated independently of both implementations, over the raw log.

    Neither the engine's running maximum nor the oracle's re-scan is consulted here: the
    expected issue is recomputed from the record log by the definition in section 5.2.
    """
    requests = [PredictionRequest("e1", moment) for moment in times]
    by_id = {record.record_id: record for record in log}
    for vector in replay(log, requests, [FORECAST]).vectors:
        target = vector.prediction_time + LEAD
        eligible = [
            record
            for record in log
            if record.valid_time == target
            and record.value is not None
            and is_visible(record.available_time, vector.prediction_time)
        ]
        chosen = vector.by_name("fc")
        if not eligible:
            assert chosen.value is None
            continue
        assert chosen.lineage
        selected = by_id[chosen.lineage[0]]
        assert selected.issued_time == max(
            record.issued_time for record in eligible if record.issued_time is not None
        )


@given(log=_forecast_log(), times=_TIMES)
@SETTINGS
def test_no_forecast_issued_after_the_prediction_time_is_ever_used(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    """The leak this operator exists to prevent, asserted directly on the lineage."""
    requests = [PredictionRequest("e1", moment) for moment in times]
    by_id = {record.record_id: record for record in log}
    for vector in replay(log, requests, [FORECAST]).vectors:
        for record_id in vector.by_name("fc").lineage:
            record = by_id[record_id]
            assert record.issued_time is not None
            assert record.issued_time <= vector.prediction_time
            assert is_visible(record.available_time, vector.prediction_time)


@st.composite
def _label_log(draw: st.DrawFn) -> list[CanonicalRecord]:
    records: list[CanonicalRecord] = []
    for index in range(draw(st.integers(min_value=0, max_value=8))):
        label_hour = draw(st.integers(min_value=0, max_value=8))
        reveal_lag = draw(st.integers(min_value=0, max_value=6))
        label_time = BASE + label_hour * HOUR
        records.append(
            CanonicalRecord(
                record_id=f"y{index:03d}",
                kind=RecordKind.LABEL,
                entity_id="e1",
                source_id="meter",
                feature_name="target",
                value=float(index),
                event_time=label_time,
                available_time=label_time + reveal_lag * HOUR,
            )
        )
    return records


@given(log=_label_log(), times=_TIMES)
@SETTINGS
def test_labels_become_usable_exactly_at_their_reveal(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Phase 2 acceptance test: delayed labels are usable only after label_available_time."""
    requests = [PredictionRequest("e1", moment) for moment in times]
    result = replay(log, requests, [])
    for vector, usable in zip(result.vectors, result.usable_labels, strict=True):
        expected = {
            record.record_id
            for record in log
            if is_label_usable(record.available_time, vector.prediction_time)
        }
        assert set(usable) == expected


@given(log=_label_log(), times=_TIMES)
@SETTINGS
def test_label_reveals_accumulate_monotonically(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    """A label, once revealed, stays revealed; the clock never takes information back."""
    requests = [PredictionRequest("e1", moment) for moment in times]
    result = replay(log, requests, [])
    for earlier, later in zip(result.usable_labels, result.usable_labels[1:], strict=False):
        assert set(earlier) <= set(later)
