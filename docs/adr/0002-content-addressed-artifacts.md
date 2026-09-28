# ADR-0002: Content-Addressed Immutable Artifacts

Sources, media, and geometry revisions are addressed by SHA-256 content hash.
Writes are atomic and deduplicated. A hash is never silently reused for bytes
with different content.

