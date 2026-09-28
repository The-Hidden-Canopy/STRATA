"""Typed identifier helpers for the STRATA domain model."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import NewType


EntityId = NewType("EntityId", str)
StateId = NewType("StateId", str)
SourceId = NewType("SourceId", str)
ObservationId = NewType("ObservationId", str)
AssertionId = NewType("AssertionId", str)
BranchId = NewType("BranchId", str)
DecisionId = NewType("DecisionId", str)
GeometryId = NewType("GeometryId", str)
ProvenanceId = NewType("ProvenanceId", str)


def uuid7() -> str:
    """Return a UUIDv7-shaped identifier using only the standard library.

    Python versions before native UUIDv7 support can still produce sortable,
    time-prefixed UUIDs. The version and variant bits follow RFC 9562.
    """
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_bits = int.from_bytes(os.urandom(10), "big")
    value = timestamp_ms << 80
    value |= 0x7 << 76
    value |= (random_bits >> 2) & ((1 << 74) - 1)
    value &= ~(0b11 << 62)
    value |= 0b10 << 62
    return str(uuid.UUID(int=value))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid7().replace('-', '')}"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A stable reference to a content-addressed artifact."""

    hash: str
    size: int
    media_type: str = "application/octet-stream"

