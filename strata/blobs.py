"""Content-addressed local blob storage."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from .ids import ArtifactRef


class BlobStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    def put_bytes(self, data: bytes, media_type: str = "application/octet-stream") -> ArtifactRef:
        digest = hashlib.sha256(data).hexdigest()
        target = self.path_for(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_suffix(".partial")
            temporary.write_bytes(data)
            temporary.replace(target)
        return ArtifactRef(digest, len(data), media_type)

    def put_file(self, source: str | Path, media_type: str | None = None) -> ArtifactRef:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        guessed = media_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        return self.put_bytes(source.read_bytes(), guessed)

    def get_bytes(self, digest: str) -> bytes:
        return self.path_for(digest).read_bytes()

    def verify(self, digest: str) -> dict[str, object]:
        target = self.path_for(digest)
        if not target.is_file():
            return {"hash": digest, "ok": False, "error": "missing blob"}
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        return {"hash": digest, "ok": actual == digest, "actual": actual, "size": target.stat().st_size}

