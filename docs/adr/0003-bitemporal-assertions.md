# ADR-0003: Bitemporal Assertions

Historical valid time and project transaction time are distinct values. Raw
expressions such as `circa 1910`, year-only dates, and open bounds are retained
alongside conservative query bounds; they are never coerced to exact days.

