"""Central control of randomness.

Section 12 of docs/research_plan.md requires randomness to be controlled centrally. Nothing
in this project may call an unseeded global random function; every stochastic component
draws from a generator derived here from a recorded seed and a purpose string.

Deriving per-purpose generators, rather than sharing one global generator, means the number
of draws made by one component cannot shift the stream seen by another. Adding a new
component therefore cannot silently change the outputs of an existing one.

The derivation uses SHA-256 rather than :func:`hash`, whose string hashing is randomized per
interpreter process unless ``PYTHONHASHSEED`` is fixed. A seed derived from :func:`hash`
would reproduce within a process and not across processes, which is the failure mode this
module exists to prevent.
"""

from __future__ import annotations

import hashlib
import random

# Distinguishes this project's derivations from any other use of the same base seed.
_NAMESPACE = "vifusion.determinism.v1"

# Seeds are reduced into the non-negative 64-bit range: wide enough that derived seeds do
# not collide in practice, and narrow enough to record in a manifest and retype by hand.
_SEED_MODULUS = 1 << 64


def derive_seed(base_seed: int, purpose: str) -> int:
    """Derive a stable sub-seed for one purpose from a recorded base seed.

    The result depends only on the arguments, so it is identical across processes,
    interpreter versions, and platforms.
    """
    material = f"{_NAMESPACE}:{base_seed}:{purpose}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % _SEED_MODULUS


def make_rng(base_seed: int, purpose: str) -> random.Random:
    """Return a generator private to ``purpose``, seeded deterministically."""
    return random.Random(derive_seed(base_seed, purpose))
