# STRATA architecture

STRATA is a local process with three layers:

```text
CLI / loopback web UI
          |
  application services
          |
 SQLite domain store + runtime adapters
```

`bundle.store.Database` is the authoritative local store. It enables WAL mode,
foreign keys, and short explicit transactions. Cross-record mutations such as
claims and check-ins use `BEGIN IMMEDIATE` so two workers cannot acquire the
same work item.

## Ready work and claims

Work is eligible when its project and phase are active, hard dependencies are
complete, the item has no active claim, and the candidate agent is an active
project member with the required capabilities and lane access. The scheduler
ranks eligible items by priority, lane preference, age, and stable ID.

A claim records its agent instance, issue time, heartbeat, expiry, and whether
the work may have side effects. A heartbeat extends the lease. Check-in closes
the claim and records artifacts and blockers. Expired side-effecting claims go
to `reconciliation`; other expired claims can return to the ready frontier.

## Public local API

The loopback server exposes versioned JSON routes under `/api/v1`. The CLI and
web UI call the same store operations. The initial surface covers projects,
phases, agents, work, pull, claim, heartbeat, check-in, release, events,
artifacts, attention, and runtime registration.

Project snapshots use the `bundle-project-1` archive format: a zip containing
JSON records for the project, phases, work, agents, dependencies, artifacts,
and events. Imported IDs are regenerated so an import cannot silently overwrite
an existing local project.

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
