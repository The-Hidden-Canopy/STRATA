# STRATA

STRATA is a local-first operating system for multi-agent project execution. It turns a project into durable work, lets eligible agents pull that work, and keeps claims, heartbeats, artifacts, and decisions locally inspectable.

The first implementation slice is deliberately standard-library-first:

- Python 3.11+
- SQLite with WAL mode
- JSON-shaped local domain records
- Generic command and HTTP runtime contracts
- CLI plus a zero-build loopback web UI

No hosted account, database server, JavaScript build, or mandatory telemetry is required.

## Quick start

```text
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -e .
bundle init
bundle project create demo --objective "Ship a small feature"
bundle project list
bundle serve
```

The UI listens on `http://127.0.0.1:8765` by default. The database lives at `.bundle/bundle.db` and is ignored by Git.

## Core loop

1. Create a project and phase.
2. Register an agent with capabilities and lane preferences.
3. Add work items and dependencies.
4. Pull the highest-ranked eligible work.
5. Claim it with an expected revision.
6. Heartbeat while executing.
7. Check in a result, blockers, or artifacts.

Claims are leases. A missing heartbeat expires a claim; side-effecting work enters reconciliation instead of being blindly retried.

## Development

```text
python -m unittest discover -s tests -v
python -m compileall -q bundle
```

See [docs/architecture.md](docs/architecture.md) for the persistence and scheduling model. The product boundary and longer-term roadmap are captured in the engineering specification supplied with this repository.
