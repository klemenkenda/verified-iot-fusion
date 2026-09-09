"""Canonical serialization and content hashing.

Section 12 of docs/research_plan.md addresses data and configuration by checksum, so every
hash in a run manifest must be reproducible on a different machine from the same bytes.
Canonical JSON here means sorted keys, no insignificant whitespace, and UTF-8 — so two
semantically equal objects with different key order hash identically.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_READ_CHUNK = 1 << 20


def canonical_json(obj: Any) -> bytes:
    """Serialize to the canonical byte form used for every content hash."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_object(obj: Any) -> str:
    """Content hash of any JSON-serializable object, insensitive to key order."""
    return sha256_bytes(canonical_json(obj))


def hash_file(path: Path) -> str:
    """Content hash of a file, read in chunks so large artifacts do not load into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_READ_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
