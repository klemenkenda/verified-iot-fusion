# Acquiring and reading the datasets

Phase 5 of [the plan](research_plan.md) builds the adapters; this file is the operating
manual for them. It says what to download, where to put it, what to run, and — for each
dataset — the one thing about its timing that a reader must decide rather than discover.

No raw data is committed. The fixtures under `tests/fixtures/datasets/` are small files in
the real formats, written to exercise the shapes each adapter exists to handle: a relayed
observation, a missing value, a QC flag, a superseded correction, a revised forecast, a
categorical column. They are not samples of the real data, which none of the three sources
permits redistributing.

## The two commands

```bash
# Read a dataset, validate it, and generate its card of checksums, ranges, and provenance.
uv run vifusion dataset-card <name> --root <dir> [--option key=value ...] [--output card.json]

# Replay a compiled feature program over it, explaining every eligibility decision.
uv run vifusion dataset-replay <name> --root <dir> --program <program.yaml> \
    [--option key=value ...] [--as-of <instant>] [--late-policy ignore|revise|retract]
```

`dataset-card` exits non-zero when the read is unsound — a naive timestamp, an identifier
naming two different records, a record with no availability derivation. Those are defects,
not descriptions.

Options that have no default are named in the error when you omit them. That is deliberate:
section 5.1 requires a dataset with no recorded availability to have its model *declared*,
and a default nobody chose is indistinguishable in the results from a measured value.

## What each adapter decides about time

| Dataset | Availability model | What is recorded | What is declared |
| --- | --- | --- | --- |
| USCRN | `bounded` | the dissemination window a record arrived in | nothing |
| Enefit | `recorded` | which rows were delivered together (`data_block_id`) | when each block was released |
| Beijing | `simulated` | nothing | the whole arrival regime |

`inferred` is the fourth model section 12 names and is deliberately not implemented: no
committed dataset needs it, and a model nothing routes through is the defect the Phase 2
audit found. It raises rather than degrading to a guess.

## NOAA USCRN — built first

Freely downloadable, no competition terms, and the only one of the three whose availability
must be *reconstructed*. That is why the build order puts it first: it exercises the whole
adapter machinery, while a dataset that hands you a delivery identifier exercises little.

Download hourly update files from the
[update archive](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/updates/) into
`data/raw/uscrn/updates/<year>/`, keeping the published filenames — the filename *is* the
availability evidence, so renaming a file destroys the derivation. Quality-controlled yearly
files go in `data/raw/uscrn/final/`.

```bash
uv run vifusion dataset-card uscrn --root data/raw/uscrn \
    --option final=final/CRNH0203-2023-CO_Boulder_14_W.txt \
    --output artifacts/cards/uscrn.json
```

**Verify the format constants on first download.** `FIELD_COUNT` and the column indices in
`src/vifusion/adapters/uscrn.py` are transcribed from the hourly02 format documentation, and
a transcription can be wrong. The adapter checks the field count of every row and refuses a
file that does not match, so the failure is loud — but check the constants against the
[readme](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/readme.txt) rather than
trusting that silence means agreement.

**The final product is a target, never an input.** It is read by a separate function into
`label` records that the feature-search surface excludes, and its publication delay is a
*simulated* parameter — NCEI does not state when each quality-controlled value was released.

## Enefit — the primary predictive dataset

Accept the competition terms and download
[the data](https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data)
into `data/raw/enefit/`. The licence shown by the host is CC BY-NC-SA 4.0; the unresolved
tension between that and this repository's MIT code licence is recorded in
[the decision log](decision_log.md) and must be settled before any public release.

```bash
uv run vifusion dataset-card enefit --root data/raw/enefit \
    --option first_block_id=0 --option first_release=2021-09-02T00:00:00Z \
    --option entities=7,9 --output artifacts/cards/enefit.json
```

**The block schedule is yours to declare.** `data_block_id` records which rows were delivered
together and in what order; it does not record *when*. Confirm the first block's identifier
and release instant against the competition documentation before the final sweep — the values
above are shaped correctly and are not authoritative.

**Global streams are broadcast per prediction unit.** Prices and weather belong to no
prosumer, but a stream is keyed by entity, so the adapter replicates them into each requested
unit. That is exact and expensive: use `--option entities=...` to work on a slice. The real
answer is the declared entity graph of section 5.3, which is not built yet.

## Beijing Multi-Site Air Quality — cross-domain

Download the twelve station files from
[UCI](https://archive.ics.uci.edu/dataset/501/beijing) into `data/raw/beijing/`, keeping the
`PRSA_Data_<Station>_<from>-<to>.csv` names.

```bash
uv run vifusion dataset-card beijing --root data/raw/beijing \
    --option arrival=typical --output artifacts/cards/beijing.json
```

**Every result is relative to an arrival scenario.** The dataset records no availability, so
`--option arrival=` is required and takes one of `prompt`, `typical`, or `staggered`, declared
in `src/vifusion/adapters/beijing.py` with the reasoning for each. The scenario name is in
every record's derivation, in the dataset card, and in the run manifest, so a result computed
under one regime cannot be read as a result computed under another. Section 10.1's sensitivity
analysis is what varies them.

## Splits

Split definitions are frozen in `configs/splits/` and hashed into every run manifest as
`split_manifest_hash` (section 9). The entity identifiers in them are placeholders chosen for
shape, and the notes in each file say so: confirm them against the real station inventory,
prediction-unit list, and station names before the final sweep.

## Late arrival

`--as-of <instant>` reads an archive as a reader holding it at that instant would have, and
applies whatever arrived later as a batch of late records under `--late-policy`. USCRN
produces these natively — its documentation states that observations may be relayed several
hours late.

The default policy is `ignore`, and it is the primary evaluation policy: prior predictions are
immutable, because a system that silently revises what it predicted yesterday cannot be
evaluated — the prediction being scored is no longer the prediction that was made. `revise`
recomputes and names what moved; `retract` flags the affected vectors while preserving their
values for audit. All three report which vectors a late record *would* have contributed to,
because declining to rewrite an output is not a reason to stop knowing about it.
