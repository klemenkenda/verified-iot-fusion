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

`tools/fetch_uscrn.py` downloads it; `data/README.md` documents that. Files keep the names the
archive publishes them with — the filename *is* the availability evidence, so renaming one
destroys the derivation. Update files go under `data/raw/uscrn/updates/<year>/` and
quality-controlled yearly files in `data/raw/uscrn/final/`.

**The update archive begins 2020-10-06 20:00 UTC.** There is no 2019 directory and no earlier
part of 2020. Those years exist as quality-controlled yearly products, but a yearly product
records no delivery time, so there is nothing to reconstruct availability from — this is a
property of what NCEI publishes, not a download that has not happened yet. It is a hard bound
on every split this repository can honestly run.

```bash
uv run vifusion dataset-card uscrn --root data/raw/uscrn \
    --option stations=94075 \
    --option final=final/CRNH0203-2023-CO_Boulder_14_W.txt \
    --output artifacts/cards/uscrn.json
```

**`--option stations=` is not optional in practice.** A year of the archive is about 8,760
files carrying roughly 160 stations, and every station is an entity whose records are held in
memory; reading the archive whole is several million records before any feature is computed.
The filter is scope and not time — it changes which entities exist, never what was knowable
about them — and the stations read are recorded in the card. A WBANNO that appears in no file
is an error rather than a smaller slice.

The archive is organised by year and each year must be downloaded separately. Check that the
years on disk cover the split you intend to run: a split whose training period predates the
oldest downloaded year produces empty folds rather than an error.

**Verify the format constants on first download.** `FIELD_COUNT` and the column indices in
`src/vifusion/adapters/uscrn.py` are transcribed from the hourly02 format documentation, and
a transcription can be wrong. The adapter checks the field count of every row and refuses a
file that does not match, so the failure is loud — but check the constants against the
[readme](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/readme.txt) rather than
trusting that silence means agreement.

**The final product is a target, never an input.** It is read by a separate function into
`label` records that the feature-search surface excludes, and its publication delay is a
*simulated* parameter — NCEI does not state when each quality-controlled value was released.

**One target file per year.** The quality-controlled product is published yearly, so a split
spanning years needs one file per year and `--option final=` takes a comma-separated list.
A run whose targets stopped at a year boundary would not fail — it would quietly score nothing
after that date.

```bash
uv run vifusion evaluate configs/tasks/uscrn_temperature_1h_archive.yaml --fold validation
```

## Enefit — the primary predictive dataset

Accept the competition terms and download
[the data](https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data)
into `data/raw/enefit/`. The licence shown by the host is CC BY-NC-SA 4.0; the unresolved
tension between that and this repository's MIT code licence is recorded in
[the decision log](decision_log.md) and must be settled before any public release.

```bash
uv run vifusion dataset-card enefit --root data/raw/enefit \
    --option first_block_id=0 --option first_release=2021-08-31T11:00:00+03:00 \
    --option entities=7,9 --output artifacts/cards/enefit.json
```

**The block schedule is yours to declare, but the data narrows it to about an hour.**
`data_block_id` records which rows were delivered together and in what order; it does not
record *when*. What the files do fix, exactly and throughout, is the *content* of each block.
Writing `D(N)` for the day block `N` asks to be predicted — empirically `2021-09-01 + N` days,
checked at blocks 0, 1, 2, 632, 633, 634 and 635 — every block holds:

| Stream | Latest instant in block `N` |
| --- | --- |
| `historical_weather` | 10:00 on the day before `D(N)` |
| `forecast_weather` | issued 02:00 the day before `D(N)`, running to the day after |
| `electricity_prices` / `gas_prices` | the day before `D(N)` |
| `client` | two days before `D(N)` |

So block `N` cannot have been released before 11:00 on the day before `D(N)` — the hour after
its last measured weather — and must have been released before `D(N)` began, or it could not
be used to predict it. The command above takes the earliest instant consistent with that
evidence, which for block 0 is **2021-08-31 11:00 EET**. Anything else inside the same window
behaves identically for a prediction of `D(N)`; the declaration is recorded in every record's
derivation regardless, so two schedules can never be confused.

**A target's block is not its arrival.** `train.csv` files a target row under the block that
*asked* for that day's prediction, and the competition hands the actual value back two blocks
later — `example_test_files/` shows it directly: iteration `data_block_id` 634 asks for
2023-05-28 and reveals the targets for 2023-05-26, which `train.csv` files under block 632.
Dating a label by its own block would make it available before the hour it describes had
happened; on the real file the very first record fails the canonical record's own check, which
is how this was found. The adapter applies the two-block lag as a recorded fact
(`LABEL_REVELATION_LAG_BLOCKS`), which puts a midnight target's arrival 35 hours after the
hour it measures.

**Global streams are broadcast per prediction unit.** Prices and weather belong to no
prosumer, but a stream is keyed by entity, so the adapter replicates them into each requested
unit. That is exact and expensive: use `--option entities=...` to work on a slice.

**Weather is not yet readable per prosumer.** `historical_weather.csv` carries 112 grid points
and `forecast_weather.csv` the matching forecasts, but a stream is keyed by
`(entity, source, feature)` — latitude and longitude distinguish a *record*, not a *stream*.
All 112 points therefore collapse onto one stream per prediction unit: 2,688 records share a
single arrival instant against a declared four per hour, and `last(temperature)` returns an
arbitrary one of 112 values spanning some five degrees. `weather_station_to_county_mapping.csv`
maps 49 of the 112 points to 15 counties and is the raw material for the declared entity graph
of section 5.3. Until that graph exists, read Enefit without the two weather files, and treat
`configs/programs/enefit_consumption.yaml` as a shape rather than a runnable program.

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
`split_manifest_hash` (section 9). The entity identifiers in them were written as placeholders
chosen for shape; the downloaded data has now been checked against them, and both sets turn out
to name real entities:

- **USCRN** — `53131` and `94074` are both WBANNO values present in the 2023 update archive, as
  is `94075`, the station of the committed final file.
- **Enefit** — `train.csv` carries 69 prediction units numbered 0 to 68, so the held-out units
  `9` and `15` exist.

The periods are settled too, but not the way they were written. `uscrn_primary` trains from
2019-01-01 and the update archive begins 2020-10-06 — so that split is not waiting on a
download, it is unsatisfiable, and no download will fix it. **`uscrn_archive` supersedes it**:
the same rationale, sized to the evidence that exists, training from 2020-10-07 to mid-2023
with quarterly validation and test periods after it. `uscrn_primary` is left in place because
section 12 forbids editing a frozen split, and its note now says why it cannot be run.

`uscrn_2023` remains beside both as a shakedown split over a single year. Three splits on one
dataset is two more than an experiment wants; each hashes differently into every run manifest,
so the one a result was computed under is never in doubt.

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
