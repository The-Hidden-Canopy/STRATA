"""Lossless historical date and interval values.

The raw expression is retained so ``circa 1910`` is never silently reduced to
an exact date. Derived bounds are used only for conservative indexing/querying.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^(\d{4})$")


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@dataclass(frozen=True, slots=True)
class HistoricalDate:
    raw: str
    earliest: date | None
    latest: date | None
    precision: str
    relation: str = "exact"

    @classmethod
    def parse(cls, value: str | date | None) -> "HistoricalDate":
        if value is None or (isinstance(value, str) and not value.strip()):
            return cls("unknown", None, None, "unknown", "unknown")
        if isinstance(value, date):
            return cls(value.isoformat(), value, value, "day")
        raw = str(value).strip()
        lowered = raw.lower()
        relation = "exact"
        body = raw
        if lowered.startswith("circa ") or lowered.startswith("c. "):
            relation, body = "circa", raw.split(" ", 1)[1]
        elif lowered.startswith("before "):
            relation, body = "before", raw.split(" ", 1)[1]
        elif lowered.startswith("after "):
            relation, body = "after", raw.split(" ", 1)[1]

        match = _DATE_RE.fullmatch(body)
        if match:
            parsed = date.fromisoformat(body)
            if relation == "before":
                return cls(raw, None, parsed - timedelta(days=1), "day", relation)
            if relation == "after":
                return cls(raw, parsed + timedelta(days=1), None, "day", relation)
            if relation == "circa":
                return cls(raw, parsed - timedelta(days=365), parsed + timedelta(days=365), "circa-day", relation)
            return cls(raw, parsed, parsed, "day")
        match = _MONTH_RE.fullmatch(body)
        if match:
            year, month = map(int, match.groups())
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            if relation == "before":
                return cls(raw, None, start - timedelta(days=1), "month", relation)
            if relation == "after":
                return cls(raw, end + timedelta(days=1), None, "month", relation)
            if relation == "circa":
                return cls(raw, date(year - 1, month, 1), date(year + 1, month, calendar.monthrange(year + 1, month)[1]), "circa-month", relation)
            return cls(raw, start, end, "month")
        match = _YEAR_RE.fullmatch(body)
        if match:
            year = int(match.group(1))
            start, end = date(year, 1, 1), date(year, 12, 31)
            if relation == "before":
                return cls(raw, None, start - timedelta(days=1), "year", relation)
            if relation == "after":
                return cls(raw, end + timedelta(days=1), None, "year", relation)
            if relation == "circa":
                return cls(raw, date(year - 1, 1, 1), date(year + 1, 12, 31), "circa-year", relation)
            return cls(raw, start, end, "year")
        raise ValueError(f"unsupported historical date: {value!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "earliest": _iso(self.earliest),
            "latest": _iso(self.latest),
            "precision": self.precision,
            "relation": self.relation,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "HistoricalDate":
        value = value or {"raw": "unknown"}
        return cls(value.get("raw", "unknown"), _date(value.get("earliest")), _date(value.get("latest")), value.get("precision", "unknown"), value.get("relation", "exact"))


@dataclass(frozen=True, slots=True)
class HistoricalInterval:
    start: HistoricalDate
    end: HistoricalDate

    @classmethod
    def parse(cls, start: str | date | None = None, end: str | date | None = None) -> "HistoricalInterval":
        return cls(HistoricalDate.parse(start), HistoricalDate.parse(end))

    def as_dict(self) -> dict[str, Any]:
        return {"start": self.start.as_dict(), "end": self.end.as_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "HistoricalInterval":
        value = value or {}
        return cls(HistoricalDate.from_dict(value.get("start")), HistoricalDate.from_dict(value.get("end")))

    def contains(self, when: str | date) -> bool:
        point = HistoricalDate.parse(when)
        if point.earliest is None:
            return False
        if self.start.latest and point.latest and point.latest < self.start.latest:
            return False
        if self.end.earliest and point.earliest and point.earliest > self.end.earliest:
            return False
        return True

    def overlaps(self, other: "HistoricalInterval") -> bool:
        if self.end.latest and other.start.earliest and self.end.latest < other.start.earliest:
            return False
        if other.end.latest and self.start.earliest and other.end.latest < self.start.earliest:
            return False
        return True


def interval(start: str | date | None = None, end: str | date | None = None) -> dict[str, Any]:
    return HistoricalInterval.parse(start, end).as_dict()


def contains(value: dict[str, Any], when: str | date) -> bool:
    return HistoricalInterval.from_dict(value).contains(when)

