"""Phase 5 acceptance test: no test labels are exposed through the feature-search interface.

The separation is structural rather than procedural, and the tests are written to that:
targets live in their own source, that source is absent from
:meth:`DatasetBundle.searchable_sources`, and the frozen split files decide which entities and
which periods an experiment may use.

**Why structural.** Restricting a proposer to the training period would still leave the target
stream itself offerable as an input, and a feature reading the target at lag zero is not
temporally wrong — no analysis in section 10 would reject it, because nothing about it is
late. The only defence that holds is that the target is not in the surface at all.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from tests.adapters.conftest import ALL_BUNDLES
from vifusion.adapters import beijing, enefit, splits, uscrn
from vifusion.adapters.base import DatasetBundle
from vifusion.adapters.splits import ExposureError, SplitError
from vifusion.dsl.schema import SourceSchema

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_DIR = REPO_ROOT / "configs" / "splits"
PROGRAM_DIR = REPO_ROOT / "configs" / "programs"

FROZEN = splits.load_all(SPLIT_DIR)


# --- the searchable surface -----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_no_target_reaches_the_feature_search_surface(name: str) -> None:
    bundle = ALL_BUNDLES[name]()
    splits.assert_no_label_exposure(bundle)
    offered = {source.source_id for source in bundle.searchable_sources()}
    assert offered.isdisjoint(bundle.label_sources)


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_the_surface_is_not_empty(name: str) -> None:
    """Guards the test above against passing because nothing is offered at all."""
    assert ALL_BUNDLES[name]().searchable_sources()


def test_the_exposure_check_fails_when_a_target_is_offered(
    uscrn_bundle: DatasetBundle,
) -> None:
    """A check that cannot fail proves nothing, so this removes the separation and looks."""
    exposed = DatasetBundle(
        dataset=uscrn_bundle.dataset,
        version=uscrn_bundle.version,
        records=uscrn_bundle.records,
        sources=uscrn_bundle.sources,
        label_sources=frozenset(),
    )
    with pytest.raises(ExposureError, match="offers targets"):
        splits.assert_no_label_exposure(exposed)


def test_uscrn_final_products_are_targets_not_inputs(uscrn_bundle: DatasetBundle) -> None:
    """Section 8.2 permits the quality-controlled product as a target only."""
    offered = {source.source_id for source in uscrn_bundle.searchable_sources()}
    assert uscrn.FINAL_SOURCE_ID not in offered
    assert uscrn.UPDATE_SOURCE_ID in offered


def test_beijing_target_shares_its_quantity_with_a_readable_stream(
    beijing_bundle: DatasetBundle,
) -> None:
    """The hardest case for the separation, and the reason it must be structural.

    Forecasting PM2.5 means the label *is* a later PM2.5 observation, so the target stream
    carries the same values as a stream a program may read. Nothing about the values keeps
    them apart; only the source does.
    """
    offered = {
        (source.source_id, source.feature_name) for source in beijing_bundle.searchable_sources()
    }
    assert (beijing.MEASUREMENT_SOURCE_ID, "pm2_5") in offered
    assert (beijing.TARGET_SOURCE_ID, "pm2_5") not in offered

    labels = {record.value for record in beijing_bundle.label_records if record.value is not None}
    measured = {
        record.value
        for record in beijing_bundle.records
        if record.source_id == beijing.MEASUREMENT_SOURCE_ID and record.feature_name == "pm2_5"
    }
    assert labels & measured, "the two streams carry the same quantity, as expected"


# --- programs agree with the adapters ---------------------------------------------------------


@pytest.mark.parametrize(
    ("program_file", "schemas"),
    [
        ("uscrn_temperature.yaml", uscrn.source_schemas()),
        ("beijing_pm25.yaml", beijing.source_schemas()),
        ("enefit_consumption.yaml", enefit.source_schemas()),
    ],
)
def test_a_program_declares_the_sources_its_adapter_produces(
    program_file: str, schemas: tuple[SourceSchema, ...]
) -> None:
    """A program that declared a unit the adapter does not produce would compile and be wrong.

    The compiler checks a program against its own declarations, which is the right thing for
    it to do — it never sees the data. Nothing else checks the declarations against the
    adapter, so this does.
    """
    document = yaml.safe_load((PROGRAM_DIR / program_file).read_text(encoding="utf-8"))
    declared = {
        (source["source_id"], source["feature_name"]): source for source in document["sources"]
    }
    produced = {(schema.source_id, schema.feature_name): schema for schema in schemas}
    for key, source in declared.items():
        assert key in produced, f"{program_file} declares {key}, which the adapter never emits"
        schema = produced[key]
        assert source.get("unit") == schema.unit, f"{key} unit"
        assert source.get("value_type", "number") == schema.value_type, f"{key} value type"
        assert source.get("kind", "measurement") == str(schema.kind), f"{key} kind"
        assert source["max_input_rate_per_hour"] == schema.max_input_rate_per_hour, f"{key} rate"


@pytest.mark.parametrize(
    ("program_file", "label_sources"),
    [
        ("uscrn_temperature.yaml", {uscrn.FINAL_SOURCE_ID}),
        ("beijing_pm25.yaml", {beijing.TARGET_SOURCE_ID}),
        ("enefit_consumption.yaml", {enefit.TARGET_SOURCE_ID}),
    ],
)
def test_no_checked_in_program_reads_a_target(program_file: str, label_sources: set[str]) -> None:
    document = yaml.safe_load((PROGRAM_DIR / program_file).read_text(encoding="utf-8"))
    declared = {source["source_id"] for source in document["sources"]}
    assert declared.isdisjoint(label_sources)


# --- frozen splits ---------------------------------------------------------------------------


def test_every_dataset_has_a_frozen_split() -> None:
    """Section 9 requires the freeze before the sweep, so a missing one is a failure now."""
    assert {split.dataset for split in FROZEN.values()} == {
        uscrn.DATASET_NAME,
        enefit.DATASET_NAME,
        beijing.DATASET_NAME,
    }


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_folds_are_chronological_and_disjoint(name: str) -> None:
    split = FROZEN[name]
    assert split.train.end <= split.validation.start
    assert split.validation.end <= split.test.start
    assert split.fold_of(split.train.start) == "train"
    assert split.fold_of(split.validation.start) == "validation"
    assert split.fold_of(split.test.start) == "test"
    # The instant a fold ends belongs to no fold: periods are half-open, and the gap is real.
    assert split.fold_of(split.train.end) is None


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_the_declared_gap_is_actually_left(name: str) -> None:
    split = FROZEN[name]
    assert split.gap > timedelta(0)
    assert split.validation.start - split.train.end >= split.gap
    assert split.test.start - split.validation.end >= split.gap


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_held_out_entities_are_absent_from_training(name: str) -> None:
    split = FROZEN[name]
    assert split.held_out_entities
    entities = (*split.held_out_entities, "some-other-entity")
    assert set(split.entities_for("train", entities)).isdisjoint(split.held_out_entities)
    assert set(split.entities_for("validation", entities)).isdisjoint(split.held_out_entities)
    assert set(split.entities_for("test", entities)) == set(entities)


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_a_split_hashes_stably(name: str) -> None:
    """The value a run manifest records as ``split_manifest_hash``."""
    reloaded = splits.load(SPLIT_DIR / f"{name}.yaml")
    assert reloaded.split_manifest_hash == FROZEN[name].split_manifest_hash
    assert len(reloaded.split_manifest_hash) == 64


def test_two_splits_of_one_dataset_hash_differently() -> None:
    """A result computed under one split must not be mistakable for another."""
    original = FROZEN["uscrn_primary"]
    longer = splits.Period(start=original.test.start, end=original.test.end + timedelta(days=1))
    moved = original.model_copy(update={"test": longer})
    assert moved.split_manifest_hash != original.split_manifest_hash


def test_overlapping_folds_are_refused() -> None:
    payload = FROZEN["uscrn_primary"].as_dict()
    payload["validation"]["start"] = payload["train"]["end"]
    with pytest.raises(SplitError, match="less than the declared gap"):
        splits.parse(payload)


def test_a_naive_boundary_is_refused() -> None:
    payload = FROZEN["uscrn_primary"].as_dict()
    payload["train"]["start"] = "2019-01-01T00:00:00"
    with pytest.raises(SplitError, match="timezone-aware"):
        splits.parse(payload)


def test_prediction_times_stay_inside_their_fold() -> None:
    split = FROZEN["uscrn_primary"]
    times = splits.prediction_times(split, "test", every=timedelta(days=7))
    assert times
    assert all(split.fold_of(moment) == "test" for moment in times)
    assert times[0] == split.test.start


def test_a_prediction_time_outside_the_fold_is_refused() -> None:
    split = FROZEN["uscrn_primary"]
    with pytest.raises(SplitError, match="outside the test period"):
        splits.prediction_times(
            split, "test", every=timedelta(days=1), start=datetime(2019, 6, 1, tzinfo=UTC)
        )
