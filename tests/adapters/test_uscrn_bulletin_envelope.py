"""The GTS bulletin envelope, and what an empty dissemination window means.

USCRN update files are archived exactly as broadcast, so each one opens with a NOAAPort/WMO
bulletin envelope rather than with data. The committed fixtures carry no envelope at all --
they were hand-built from the column documentation -- so until the real archive was downloaded
this whole path ran only against files nobody had checked. It broke immediately: a 2021 file
carries *three* envelopes and no data rows, and the adapter refused it as a column-layout
error.

What is tested here is both halves of the rule. Complete envelopes are peeled from the front,
however many there are; anything that only partly looks like an envelope is still an error,
because a file this adapter does not understand must not be parsed into plausible wrong
numbers. These use written files rather than the archive, so they run everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vifusion.adapters import uscrn
from vifusion.adapters.base import AdapterError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "datasets" / "uscrn"

ENVELOPE = "****0000037610****\nSXXX91 KWBC 011240\nCRNH02\n"
"""One bulletin envelope: start-of-message marker, WMO abbreviated heading, product id."""


def _sample_row() -> str:
    """One real fixed-width row, taken from the committed fixture.

    Read rather than written out here for two reasons. A hand-composed row is a guess about the
    column layout -- the first version of this file guessed 35 fields where the format has 38 --
    and a row copied into a test drifts from the fixture it was copied from. Reading it means
    these tests exercise the same bytes the rest of the suite does.
    """
    fixture = next(FIXTURES.glob("updates/*/CRN60H0203-*.txt"))
    for line in fixture.read_text(encoding="utf-8").splitlines():
        if len(line.split()) == uscrn.FIELD_COUNT:
            return line
    raise AssertionError(f"no {uscrn.FIELD_COUNT}-field row in {fixture}")


ROW = _sample_row()


def _window_name(hours_after_observation: int = 1) -> str:
    """An update filename whose window closes after the sample row was observed.

    Derived rather than written down: the stamp is the window's *close*, and a name that closed
    before its own observation is refused by the availability model -- correctly, and it would
    make this file a test of that rule instead of a test of the envelope.
    """
    observed = datetime.strptime(ROW.split()[1] + ROW.split()[2], "%Y%m%d%H%M").replace(tzinfo=UTC)
    close = observed + timedelta(hours=hours_after_observation)
    return f"CRN60H0203-{close:%Y%m%d%H%M}.txt"


def _write(tmp_path: Path, body: str, name: str | None = None) -> Path:
    path = tmp_path / (name or _window_name())
    path.write_text(body, encoding="utf-8")
    return path


def test_one_envelope_is_skipped(tmp_path: Path) -> None:
    rows = list(uscrn._rows(_write(tmp_path, ENVELOPE + ROW + "\n")))
    assert len(rows) == 1
    assert rows[0][1][0] == ROW.split()[0]


def test_several_envelopes_in_one_file_are_all_skipped(tmp_path: Path) -> None:
    """Measured on the real archive: two files of 22,439 open with three envelopes.

    Before this was handled, such a file was reported as a column-layout error -- the loudest
    possible way to be wrong about a file that is in fact perfectly well formed.
    """
    rows = list(uscrn._rows(_write(tmp_path, ENVELOPE * 3 + ROW + "\n")))
    assert len(rows) == 1


def test_an_empty_dissemination_window_reads_as_no_records(tmp_path: Path) -> None:
    """251 of 22,439 real files carry an envelope and nothing else.

    That is a fact about the hour, not damage to the file: the archive delivered nothing. It
    has to read cleanly and contribute no records, because the resulting gap is exactly what
    ``staleness`` and ``missing_count`` exist to see.
    """
    assert uscrn.EMPTY_WINDOWS_ARE_DATA
    assert list(uscrn._rows(_write(tmp_path, ENVELOPE * 3))) == []
    assert list(uscrn._rows(_write(tmp_path, ENVELOPE))) == []


def test_an_empty_window_does_not_stop_the_archive_being_read(tmp_path: Path) -> None:
    """The end-to-end version: an empty hour beside a full one yields the full one."""
    updates = tmp_path / "updates"
    updates.mkdir()
    _write(updates, ENVELOPE * 3, _window_name(2))
    _write(updates, ENVELOPE + ROW + "\n", _window_name(1))
    bundle = uscrn.read_updates(updates, root=tmp_path, features=["t_hr_avg"])
    assert len(bundle.records) == 1
    assert bundle.records[0].entity_id == ROW.split()[0]


def test_a_file_with_no_envelope_at_all_is_still_read(tmp_path: Path) -> None:
    """The committed fixtures are exactly this shape, and must keep working."""
    rows = list(uscrn._rows(_write(tmp_path, ROW + "\n")))
    assert len(rows) == 1


@pytest.mark.parametrize(
    ("body", "why"),
    [
        ("****0000037610****\nSXXX91 KWBC 011240\n" + ROW + "\n", "product id line missing"),
        ("****0000037610****\nCRNH02\n" + ROW + "\n", "WMO heading missing"),
        ("SXXX91 KWBC 011240\nCRNH02\n" + ROW + "\n", "start marker missing"),
    ],
)
def test_a_partial_envelope_is_an_error_rather_than_a_guess(
    tmp_path: Path, body: str, why: str
) -> None:
    """The safety property the all-three-or-none rule exists for.

    A file whose header this adapter does not recognise is a file it does not understand, and
    parsing it anyway would assign values to the wrong columns -- producing a plausible wrong
    number instead of a failure.
    """
    with pytest.raises(AdapterError, match="fields, not 38"):
        list(uscrn._rows(_write(tmp_path, body)))
    assert why  # named in the parameter list so a failure says which shape broke


def test_an_envelope_marker_after_the_opening_run_is_still_an_error(tmp_path: Path) -> None:
    """No real file does this -- checked across 22,439 -- so it is something unrecognised."""
    with pytest.raises(AdapterError, match="fields, not 38"):
        list(uscrn._rows(_write(tmp_path, ENVELOPE + ROW + "\n" + ENVELOPE + ROW + "\n")))
