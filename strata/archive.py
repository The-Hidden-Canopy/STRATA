"""ZIP-compatible ``.strata`` project exchange."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from .project import StrataProject


def pack_project(root: str | Path, archive_path: str | Path) -> Path:
    project = StrataProject.open(root)
    try:
        project.db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        project.db.conn.commit()
        target = Path(archive_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(project.root.rglob("*")):
                if not path.is_file() or path.name.endswith(("-wal", "-shm")) or ".git" in path.parts or "cache" in path.parts or "logs" in path.parts:
                    continue
                archive.write(path, path.relative_to(project.root).as_posix())
        return target
    finally:
        project.close()


def unpack_project(archive_path: str | Path, destination: str | Path) -> Path:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        root = target.resolve()
        for member in archive.infolist():
            output = (target / member.filename).resolve()
            if root != output and root not in output.parents:
                raise ValueError(f"archive path escapes destination: {member.filename}")
        archive.extractall(target)
    for directory in ("blobs", "previews", "exports", "cache", "logs"):
        (target / directory).mkdir(parents=True, exist_ok=True)
    return target
