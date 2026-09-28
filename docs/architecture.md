# STRATA architecture

STRATA is a local process with three layers:

```text
CLI / loopback web UI
          |
  application services
          |
 SQLite domain store + runtime adapters
```

`strata.storage.sqlite.SQLiteStore` is the authoritative local store. It owns
the SQLite connection, enables WAL mode and foreign keys, and wraps mutations
in short explicit transactions. STRATA schema changes are applied through the
versioned migration runner before the domain store is opened.

The native project table is `strata_project`. STRATA records reference it
directly, so the spatial-temporal engine does not depend on an unrelated
execution or scheduling database.

## Public local API

The loopback server exposes versioned JSON routes under `/api/v1`. The CLI and
web UI call the same STRATA store operations. The core surface covers project
metadata, entities, sources, branches, scene compilation, and integrity
diagnostics. Project archives retain the complete portable directory form,
including the manifest, SQLite metadata, and content-addressed blobs.

The web server binds to `127.0.0.1` by default. It is intentionally not a
remote multi-user service; operators must add an authenticated boundary before
binding it to a non-loopback interface.

## Spatial-temporal core

The `strata` package adds the specification-facing model. `manifest.json` is
human-readable and identifies the canonical CRS, local ENU origin, default
branch, and default time. `project.db` stores normalized entities, states,
events, sources, observations, assertions, branches, decisions, geometry,
spatial anchors, provenance, import jobs, and notes. `blobs/` stores immutable
SHA-256-addressed source bytes and derived assets.

Compilation is deterministic for a project, branch, time, compiler version,
configuration, and seed. The output keeps STRATA entity/state IDs in
`scene.json`, `scene.gltf`, `citations.json`, and `provenance.json`. The native
C++20 target in `cpp/` exposes the stable typed-ID and uncertainty contracts for
future SQLite, PROJ, GDAL, renderer, and desktop adapters.

The authoritative path is:

```text
source bytes -> blob hash -> source -> observation -> assertion
-> branch decision -> temporal state -> compiled scene -> renderer adapter
```
