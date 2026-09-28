"""Command-line interface for the local STRATA service."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scheduler import pull
from .portable import export_project, import_project
from .service import open_database
from .store import BundleError
from .web.server import serve


def _json_print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bundle", description="Local-first multi-agent project execution")
    parser.add_argument("--db", default=".bundle/bundle.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize a STRATA database")
    init.add_argument("path", nargs="?", default=".bundle/bundle.db")

    project = sub.add_parser("project", help="manage projects")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    pcreate = project_sub.add_parser("create")
    pcreate.add_argument("name")
    pcreate.add_argument("--description", default="")
    pcreate.add_argument("--objective", default="")
    project_sub.add_parser("list")

    phase = sub.add_parser("phase", help="manage phases")
    phase_sub = phase.add_subparsers(dest="phase_command", required=True)
    phase_create = phase_sub.add_parser("create")
    phase_create.add_argument("project")
    phase_create.add_argument("name")
    phase_create.add_argument("--objective", default="")

    agent = sub.add_parser("agent", help="manage project agents")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_create = agent_sub.add_parser("create")
    agent_create.add_argument("project")
    agent_create.add_argument("name")
    agent_create.add_argument("--capability", action="append", default=[])
    agent_create.add_argument("--lane", default="core")
    agent_create.add_argument("--secondary-lane", action="append", default=[])
    agent_list = agent_sub.add_parser("list")
    agent_list.add_argument("project")

    work = sub.add_parser("work", help="manage work items")
    work_sub = work.add_subparsers(dest="work_command", required=True)
    work_create = work_sub.add_parser("create")
    work_create.add_argument("project")
    work_create.add_argument("title")
    work_create.add_argument("--objective", default="")
    work_create.add_argument("--detail", default="")
    work_create.add_argument("--lane", default="core")
    work_create.add_argument("--priority", type=int, default=0)
    work_create.add_argument("--capability", action="append", default=[])
    work_create.add_argument("--depends-on", action="append", default=[])
    work_create.add_argument("--side-effecting", action="store_true")
    work_list = work_sub.add_parser("list")
    work_list.add_argument("project")
    work_list.add_argument("--status")
    work_ready = work_sub.add_parser("ready")
    work_ready.add_argument("project")
    work_pull = work_sub.add_parser("pull")
    work_pull.add_argument("project")
    work_pull.add_argument("agent")
    claim = work_sub.add_parser("claim")
    claim.add_argument("work")
    claim.add_argument("agent")
    claim.add_argument("revision", type=int)
    claim.add_argument("--ttl", type=int, default=120)

    heartbeat = sub.add_parser("heartbeat")
    heartbeat.add_argument("claim")
    heartbeat.add_argument("--state", default="working")
    heartbeat.add_argument("--action", default="")
    heartbeat.add_argument("--progress", default="")

    checkin = sub.add_parser("checkin")
    checkin.add_argument("claim")
    checkin.add_argument("--outcome", default="complete", choices=["complete", "blocked", "needs_review", "retryable_failure", "final_failure", "released"])
    checkin.add_argument("--summary", default="")

    runtime = sub.add_parser("runtime", help="manage runtime adapters")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_add = runtime_sub.add_parser("add")
    runtime_add.add_argument("kind")
    runtime_add.add_argument("--identity")
    runtime_sub.add_parser("list")

    export_cmd = sub.add_parser("export", help="export a portable project archive")
    export_cmd.add_argument("project")
    export_cmd.add_argument("path")
    import_cmd = sub.add_parser("import", help="import a portable project archive")
    import_cmd.add_argument("path")

    serve_cmd = sub.add_parser("serve", help="start the local web UI")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            from .store import Database
            Database(args.path).close()
            print(f"initialized {Path(args.path)}")
            return 0
        db = open_database(args.db)
        if args.command == "project" and args.project_command == "create":
            _json_print(db.create_project(args.name, args.description, args.objective))
        elif args.command == "project" and args.project_command == "list":
            _json_print(db.list_projects())
        elif args.command == "phase":
            _json_print(db.create_phase(args.project, args.name, args.objective))
        elif args.command == "agent" and args.agent_command == "create":
            _json_print(db.create_agent(args.project, args.name, args.capability, args.lane, args.secondary_lane))
        elif args.command == "agent" and args.agent_command == "list":
            _json_print(db.list_agents(args.project))
        elif args.command == "work" and args.work_command == "create":
            _json_print(db.create_work(args.project, args.title, args.objective, args.detail, None, args.lane, args.priority, args.capability, [], args.depends_on, side_effecting=args.side_effecting))
        elif args.command == "work" and args.work_command == "list":
            _json_print(db.list_work(args.project, args.status))
        elif args.command == "work" and args.work_command == "ready":
            db.recompute_ready(args.project)
            _json_print(db.list_work(args.project, "ready"))
        elif args.command == "work" and args.work_command == "pull":
            _json_print(pull(db, args.project, args.agent))
        elif args.command == "work" and args.work_command == "claim":
            _json_print(db.claim(args.work, args.agent, args.revision, ttl_seconds=args.ttl))
        elif args.command == "heartbeat":
            _json_print(db.heartbeat(args.claim, args.state, args.action, args.progress))
        elif args.command == "checkin":
            _json_print(db.checkin(args.claim, args.outcome, args.summary))
        elif args.command == "runtime" and args.runtime_command == "add":
            _json_print(db.add_runtime(args.kind, {}, args.identity))
        elif args.command == "runtime" and args.runtime_command == "list":
            _json_print(db.list_runtimes())
        elif args.command == "export":
            _json_print({"archive": str(export_project(db, args.project, args.path))})
        elif args.command == "import":
            _json_print(import_project(db, args.path))
        elif args.command == "serve":
            server = serve(db, args.host, args.port)
            print(f"STRATA UI listening on http://{args.host}:{args.port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        return 0
    except BundleError as exc:
        print(f"bundle: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
