"""Canonical serialization and content hashing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from vifusion.hashing import canonical_json, hash_file, hash_object, sha256_bytes


def test_key_order_does_not_change_the_hash() -> None:
    assert hash_object({"a": 1, "b": 2}) == hash_object({"b": 2, "a": 1})


def test_nested_key_order_does_not_change_the_hash() -> None:
    assert hash_object({"x": {"a": 1, "b": [1, {"p": 0, "q": 1}]}}) == hash_object(
        {"x": {"b": [1, {"q": 1, "p": 0}], "a": 1}}
    )


def test_list_order_does_change_the_hash() -> None:
    """Order is meaningful in a sequence and must not be normalised away."""
    assert hash_object([1, 2]) != hash_object([2, 1])


def test_canonical_form_has_no_insignificant_whitespace() -> None:
    assert canonical_json({"a": 1, "b": "x"}) == b'{"a":1,"b":"x"}'


def test_non_ascii_survives_round_trip() -> None:
    assert canonical_json({"k": "Jožef"}) == '{"k":"Jožef"}'.encode()


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_refused(value: float) -> None:
    """NaN and infinity are not JSON, and would hash to a form nothing can read back."""
    with pytest.raises(ValueError, match=r"Out of range|not JSON compliant"):
        canonical_json({"v": value})


def test_file_hash_matches_byte_hash(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    payload = b"vifusion" * 1000
    path.write_bytes(payload)
    assert hash_file(path) == sha256_bytes(payload)


def test_empty_file_hashes(tmp_path: Path) -> None:
    path = tmp_path / "empty"
    path.write_bytes(b"")
    assert hash_file(path) == sha256_bytes(b"")
