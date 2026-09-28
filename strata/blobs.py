"""Content-addressed local blob storage."""

from __future__ import annotations

import hashlib
import io
import mimetypes
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from .ids import ArtifactRef


class BlobStore:
    CHUNK_SIZE = 8 * 1024 * 1024

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    def put_bytes(self, data: bytes, media_type: str = "application/octet-stream") -> ArtifactRef:
        return self.put_stream(io.BytesIO(data), media_type=media_type)

    def put_stream(self, stream: BinaryIO, media_type: str = "application/octet-stream") -> ArtifactRef:
        """Hash and store a stream with bounded memory usage."""
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        hasher = hashlib.sha256()
        size = 0
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix="blob-", suffix=".partial", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := stream.read(self.CHUNK_SIZE):
                    hasher.update(chunk)
                    temporary.write(chunk)
                    size += len(chunk)
            digest = hasher.hexdigest()
            target = self.path_for(digest)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                temporary_path.unlink(missing_ok=True)
            else:
                temporary_path.replace(target)
            return ArtifactRef(digest, size, media_type)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def put_file(self, source: str | Path, media_type: str | None = None) -> ArtifactRef:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        guessed = media_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        with source.open("rb") as stream:
            return self.put_stream(stream, media_type=guessed)

    def open(self, digest: str, mode: str = "rb"):
        return self.path_for(digest).open(mode)

    def copy_to(self, digest: str, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.open(digest, "rb") as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, self.CHUNK_SIZE)
        return target

    def get_bytes(self, digest: str) -> bytes:
        return self.path_for(digest).read_bytes()

    def verify(self, digest: str) -> dict[str, object]:
        target = self.path_for(digest)
        if not target.is_file():
            return {"hash": digest, "ok": False, "error": "missing blob"}
        return self.verify_streaming(digest)

    def verify_streaming(self, digest: str) -> dict[str, object]:
        target = self.path_for(digest)
        if not target.is_file():
            return {"hash": digest, "ok": False, "error": "missing blob"}
        hasher = hashlib.sha256()
        size = 0
        with target.open("rb") as stream:
            while chunk := stream.read(self.CHUNK_SIZE):
                hasher.update(chunk)
                size += len(chunk)
        actual = hasher.hexdigest()
        return {"hash": digest, "ok": actual == digest, "actual": actual, "size": size}
