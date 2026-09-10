"""The declared entity graph: which weather stations sit in a prediction unit's county.

Section 5.3 and vifusion/dsl/schema.py both name a declared entity graph as the prerequisite
for cross-entity operators, and neither says what it should contain. This is that graph for
Enefit, built from two files already in the competition download --
``weather_station_to_county_mapping.csv`` and ``train.csv`` -- rather than inferred or
learned. Reading it does not yet let a feature program consume it; the cross-entity operators
that would are the deferred half of this work.

The real download exposed one thing worth its own test: the mapping file's coordinates do not
string-match the weather files' own -- some latitudes serialise as ``58.49999999999999`` where
``historical_weather.csv`` writes ``58.5``, the same float with a different repr -- so an exact
string join would silently drop every affected station. Checked against the real archive: a
round-to-a-tenth-of-a-degree join resolves all 49 mapped stations with zero mismatches.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.adapters.conftest import ENEFIT_ROOT
from vifusion.adapters import enefit
from vifusion.adapters.base import AdapterError


def test_a_units_county_maps_to_its_stations() -> None:
    """The fixture's shape: one grid point, one county, both fixture units in it."""
    graph = enefit.station_graph(ENEFIT_ROOT)
    assert graph["7"] == ("station:59.0:25.5",)
    assert graph["9"] == ("station:59.0:25.5",)


def test_a_unit_in_an_unmapped_county_maps_to_no_station(tmp_path: Path) -> None:
    """County 12 is literally ``"UNKNOWN"``, and 63 of the real archive's 112 grid points are
    not mapped to any county at all -- an empty tuple is the honest answer, not an error."""
    (tmp_path / "train.csv").write_text(
        "county,is_business,product_type,target,is_consumption,datetime,data_block_id,"
        "row_id,prediction_unit_id\n"
        "12,0,1,1.0,1,2021-09-01 09:00:00,1,0,42\n",
        encoding="utf-8",
    )
    (tmp_path / "weather_station_to_county_mapping.csv").write_text(
        "county_name,longitude,latitude,county\nHarjumaa,25.5,59.0,0\n", encoding="utf-8"
    )
    (tmp_path / "historical_weather.csv").write_text(
        "datetime,temperature,shortwave_radiation,latitude,longitude,data_block_id\n"
        "2021-09-01 09:00:00,14.2,320.0,59.0,25.5,1\n",
        encoding="utf-8",
    )
    assert enefit.station_graph(tmp_path) == {"42": ()}


def test_a_mismatched_grid_point_is_an_error_not_a_dropped_station(tmp_path: Path) -> None:
    """The mapping and the weather archive naming a grid point the other does not have is a
    disagreement about the grid, not something to paper over by omitting the station."""
    (tmp_path / "train.csv").write_text(
        "county,is_business,product_type,target,is_consumption,datetime,data_block_id,"
        "row_id,prediction_unit_id\n"
        "0,0,1,1.0,1,2021-09-01 09:00:00,1,0,7\n",
        encoding="utf-8",
    )
    (tmp_path / "weather_station_to_county_mapping.csv").write_text(
        "county_name,longitude,latitude,county\nHarjumaa,99.9,59.0,0\n", encoding="utf-8"
    )
    (tmp_path / "historical_weather.csv").write_text(
        "datetime,temperature,shortwave_radiation,latitude,longitude,data_block_id\n"
        "2021-09-01 09:00:00,14.2,320.0,59.0,25.5,1\n",
        encoding="utf-8",
    )
    with pytest.raises(AdapterError, match="does not carry"):
        enefit.station_graph(tmp_path)


def test_a_noisy_float_coordinate_still_joins_to_the_clean_one(tmp_path: Path) -> None:
    """The finding from the real download: 58.49999999999999 and 58.5 are the same station."""
    (tmp_path / "train.csv").write_text(
        "county,is_business,product_type,target,is_consumption,datetime,data_block_id,"
        "row_id,prediction_unit_id\n"
        "0,0,1,1.0,1,2021-09-01 09:00:00,1,0,7\n",
        encoding="utf-8",
    )
    (tmp_path / "weather_station_to_county_mapping.csv").write_text(
        "county_name,longitude,latitude,county\nHarjumaa,25.5,58.49999999999999,0\n",
        encoding="utf-8",
    )
    (tmp_path / "historical_weather.csv").write_text(
        "datetime,temperature,shortwave_radiation,latitude,longitude,data_block_id\n"
        "2021-09-01 09:00:00,14.2,320.0,58.5,25.5,1\n",
        encoding="utf-8",
    )
    assert enefit.station_graph(tmp_path) == {"7": ("station:58.5:25.5",)}


def test_no_mapping_file_is_an_empty_graph_not_an_error(tmp_path: Path) -> None:
    """Naming stations is optional context; a competition download without it still reads."""
    (tmp_path / "train.csv").write_text(
        "county,is_business,product_type,target,is_consumption,datetime,data_block_id,"
        "row_id,prediction_unit_id\n"
        "0,0,1,1.0,1,2021-09-01 09:00:00,1,0,7\n",
        encoding="utf-8",
    )
    assert enefit.station_graph(tmp_path) == {}
