"""Renderer adapter contracts; renderers never become historical authority."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AdapterResult:
    adapter: str
    output: str
    proposed_revision: bool = True
    metadata: dict[str, Any] | None = None


class RendererAdapter(Protocol):
    name: str

    def export(self, scene: dict[str, Any], output: str | Path) -> AdapterResult:
        ...


class VantaAdapter:
    name = "vanta"

    def export(self, scene: dict[str, Any], output: str | Path) -> AdapterResult:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        import json

        path.write_text(json.dumps({"format": "strata-vanta-1", "scene": scene, "proposed_revision": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return AdapterResult(self.name, str(path), True, {"source_of_truth": "STRATA"})
