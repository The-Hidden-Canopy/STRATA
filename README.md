# STRATA

STRATA is a local-first, renderer-independent spatial-temporal evidence and reconstruction engine for rebuilding the same physical place across time from maps, photographs, terrain, records, 3D geometry, and historical documents.

The project is designed for open-source, offline work:

- portable directory-form `strata` projects;
- human-readable `manifest.json` plus SQLite metadata;
- SHA-256 content-addressed source blobs;
- lossless historical dates and uncertain intervals;
- evidence, observations, assertions, branches, and provenance as separate records;
- deterministic scene compilation and renderer-neutral exports;
- a build-free local workbench served on loopback.

No account, hosted database, telemetry, or mandatory cloud service is required.

## Quick Start

```text
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -e .

strata init demo.strata --title "Historic Downtown"
strata import geojson map.geojson --project demo.strata
strata entity create building --name "Old Hotel" --project demo.strata
strata compile --project demo.strata --time 1920 --branch main --output build/1920
strata serve --project demo.strata
```

Open the printed loopback URL in a browser. The local workbench provides temporal navigation, scene inspection, evidence browsing, branch selection, and scene export.

## Project Layout

A STRATA project is portable and self-contained:

```text
demo.strata/
  manifest.json
  project.db
  blobs/       # content-addressed source bytes
  previews/    # disposable previews
  exports/     # generated packages
  cache/       # disposable cache
  logs/        # local diagnostics
```

The authoritative SQLite schema is owned by STRATA and is migration-versioned. Existing v1 projects migrate to the native `strata_project` table when opened for writing. Read-only inspection refuses unsupported or unmigrated schemas instead of relabeling them.

## Core Model

```text
source bytes
    |
content-addressed blob
    |
source -> source region -> observation -> assertion
                                      |
                              branch decision
                                      |
                             temporal entity state
                                      |
                              compiled scene package
```

Evidence is not historical truth by itself. Assertions retain their support and uncertainty, and branches preserve competing interpretations without overwriting the base project.

## Development

```text
python -m unittest discover -s tests -v
python -m compileall -q strata
cmake -S . -B build/cmake
cmake --build build/cmake --config Release
ctest --test-dir build/cmake -C Release --output-on-failure
```

See [docs/architecture.md](docs/architecture.md) for the storage and reconstruction model. The repository-aligned engineering plan is the roadmap for migrations, native-core work, geometry, evidence registration, and renderer interoperability.
