"""The standalone STRATA command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .archive import pack_project
from .compiler import SceneCompiler
from .importers import import_file
from .project import StrataProject
from .temporal import interval
from .verify import doctor_project, verify_project


def _json_value(value: str, default: Any) -> Any:
    if not value:
        return default
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)


def _project(path: str, *, mode: str = "read") -> StrataProject:
    return StrataProject.open(path, mode=mode)


def _command_mode(args: argparse.Namespace) -> str:
    if args.command in {"entity", "state", "event", "source", "import", "observation", "assertion", "decision", "geometry"}:
        return "write"
    if args.command == "branch" and args.branch_command in {"create", "merge"}:
        return "write"
    return "read"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="strata", description="Local-first temporal evidence and reconstruction engine")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a local STRATA project")
    init.add_argument("path")
    init.add_argument("--title")
    init.add_argument("--description", default="")
    init.add_argument("--crs-authority", default="")
    init.add_argument("--crs-code", type=int)

    entity = commands.add_parser("entity", help="manage persistent place entities")
    entity_sub = entity.add_subparsers(dest="entity_command", required=True)
    entity_create = entity_sub.add_parser("create")
    entity_create.add_argument("entity_type")
    entity_create.add_argument("--name", required=True)
    entity_create.add_argument("--project", default=".")
    entity_list = entity_sub.add_parser("list")
    entity_list.add_argument("--project", default=".")
    entity_list.add_argument("--type")

    state = commands.add_parser("state", help="manage temporal entity states")
    state_add = state.add_subparsers(dest="state_command", required=True).add_parser("add")
    state_add.add_argument("entity_id")
    state_add.add_argument("--project", default=".")
    state_add.add_argument("--valid-from", default="unknown")
    state_add.add_argument("--valid-to", default="unknown")
    state_add.add_argument("--properties", default="{}")
    state_add.add_argument("--uncertainty", default="{}")
    state_add.add_argument("--geometry-id")
    state_add.add_argument("--geometry-class", choices=["observed", "documented", "inferred", "procedural", "speculative", "synthetic"], default="inferred")

    event = commands.add_parser("event", help="record explicit temporal changes")
    event_add = event.add_subparsers(dest="event_command", required=True).add_parser("add")
    event_add.add_argument("entity_id")
    event_add.add_argument("--type", required=True)
    event_add.add_argument("--project", default=".")
    event_add.add_argument("--occurred-from", default="unknown")
    event_add.add_argument("--occurred-to", default="unknown")
    event_add.add_argument("--effects", default="[]")
    event_add.add_argument("--evidence", default="[]")

    source = commands.add_parser("source", help="register evidence sources")
    source_add = source.add_subparsers(dest="source_command", required=True).add_parser("add")
    source_add.add_argument("--project", default=".")
    source_add.add_argument("--title", required=True)
    source_add.add_argument("--kind", default="text")
    source_add.add_argument("--uri", default="")
    source_add.add_argument("--hash")

    importer = commands.add_parser("import", help="hash and register an evidence file")
    importer.add_argument("kind", choices=["image", "map", "pdf", "geotiff", "geojson", "csv", "las", "laz", "gltf", "obj", "text", "binary"])
    importer.add_argument("path")
    importer.add_argument("--project", default=".")
    importer.add_argument("--title")

    observation = commands.add_parser("observation", help="record an observation from a source")
    observation_add = observation.add_subparsers(dest="observation_command", required=True).add_parser("add")
    observation_add.add_argument("source_id")
    observation_add.add_argument("--project", default=".")
    observation_add.add_argument("--entity-id")
    observation_add.add_argument("--observed", required=True)
    observation_add.add_argument("--extraction", default="{}")
    observation_add.add_argument("--review-state", default="unreviewed")

    assertion = commands.add_parser("assertion", help="record an interpreted claim")
    assertion_add = assertion.add_subparsers(dest="assertion_command", required=True).add_parser("add")
    assertion_add.add_argument("entity_id")
    assertion_add.add_argument("property_path")
    assertion_add.add_argument("--value", required=True)
    assertion_add.add_argument("--project", default=".")
    assertion_add.add_argument("--valid-from", default="unknown")
    assertion_add.add_argument("--valid-to", default="unknown")
    assertion_add.add_argument("--uncertainty", default="{}")
    assertion_add.add_argument("--status", default="proposed")
    assertion_add.add_argument("--observation-id", action="append", default=[])

    branch = commands.add_parser("branch", help="manage competing reconstructions")
    branch_sub = branch.add_subparsers(dest="branch_command", required=True)
    branch_create = branch_sub.add_parser("create")
    branch_create.add_argument("name")
    branch_create.add_argument("--project", default=".")
    branch_create.add_argument("--parent")
    branch_create.add_argument("--description", default="")
    branch_list = branch_sub.add_parser("list")
    branch_list.add_argument("--project", default=".")
    branch_diff = branch_sub.add_parser("diff")
    branch_diff.add_argument("left")
    branch_diff.add_argument("right")
    branch_diff.add_argument("--project", default=".")
    branch_merge = branch_sub.add_parser("merge")
    branch_merge.add_argument("target")
    branch_merge.add_argument("source")
    branch_merge.add_argument("--project", default=".")

    decision = commands.add_parser("decision", help="record a branch reconstruction decision")
    decision_add = decision.add_subparsers(dest="decision_command", required=True).add_parser("add")
    decision_add.add_argument("branch")
    decision_add.add_argument("action", choices=["accept", "reject", "unresolved"])
    decision_add.add_argument("--project", default=".")
    decision_add.add_argument("--entity-id")
    decision_add.add_argument("--assertion-id")
    decision_add.add_argument("--rationale", default="")

    geometry = commands.add_parser("geometry", help="register renderer-neutral geometry")
    geometry_add = geometry.add_subparsers(dest="geometry_command", required=True).add_parser("add")
    geometry_add.add_argument("kind")
    geometry_add.add_argument("--project", default=".")
    geometry_add.add_argument("--geometry", required=True)
    geometry_add.add_argument("--metadata", default="{}")

    compile_cmd = commands.add_parser("compile", help="compile a time slice into a scene package")
    compile_cmd.add_argument("--project", default=".")
    compile_cmd.add_argument("--time", required=True)
    compile_cmd.add_argument("--branch", default="main")
    compile_cmd.add_argument("--output", required=True)
    compile_cmd.add_argument("--seed", type=int, default=0)

    export = commands.add_parser("export", help="write portable render or project outputs")
    export_sub = export.add_subparsers(dest="export_command", required=True)
    export_gltf = export_sub.add_parser("gltf")
    export_gltf.add_argument("--project", default=".")
    export_gltf.add_argument("--time", required=True)
    export_gltf.add_argument("--branch", default="main")
    export_gltf.add_argument("--output", required=True)
    export_vanta = export_sub.add_parser("vanta")
    export_vanta.add_argument("--project", default=".")
    export_vanta.add_argument("--time", required=True)
    export_vanta.add_argument("--branch", default="main")
    export_vanta.add_argument("--output", required=True)
    export_web = export_sub.add_parser("web")
    export_web.add_argument("--project", default=".")
    export_web.add_argument("--time", required=True)
    export_web.add_argument("--branch", default="main")
    export_web.add_argument("--output", required=True)
    export_project_cmd = export_sub.add_parser("project")
    export_project_cmd.add_argument("--project", default=".")
    export_project_cmd.add_argument("--output", required=True)

    verify = commands.add_parser("verify", help="validate project references, blobs, and temporal data")
    verify.add_argument("project", nargs="?", default=".")
    doctor = commands.add_parser("doctor", help="diagnose project health and writable paths")
    doctor.add_argument("project", nargs="?", default=".")
    serve = commands.add_parser("serve", help="serve a local read-only STRATA inspection surface")
    serve.add_argument("--project", default=".")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8766)
    return parser


def _emit(value: Any, machine: bool = True) -> None:
    if isinstance(value, Path):
        value = str(value)
    if machine or isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            crs = {"authority": args.crs_authority, "code": args.crs_code} if args.crs_authority or args.crs_code else {}
            with StrataProject.create(args.path, args.title or Path(args.path).name, args.description, crs) as project:
                _emit({"project": str(project.root), "project_id": project.project_id, "manifest": project.manifest})
            return 0
        if args.command == "verify":
            report = verify_project(args.project)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.command == "doctor":
            report = doctor_project(args.project)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.command == "serve":
            from .web import serve as serve_project

            project = _project(args.project, mode="read")
            server = serve_project(project, args.host, args.port)
            print(f"STRATA web surface listening on http://{args.host}:{server.server_port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.shutdown()
                server.server_close()
                project.close()
            return 0
        with _project(getattr(args, "project", "."), mode=_command_mode(args)) as project:
            db = project.db
            if args.command == "entity":
                result = db.create_entity(project.project_id, args.entity_type, args.name) if args.entity_command == "create" else db.list_entities(project.project_id, args.type)
            elif args.command == "state":
                result = db.add_state(args.entity_id, interval(args.valid_from, args.valid_to), _json_value(args.properties, {}), args.geometry_id, _json_value(args.uncertainty, {}), args.geometry_class)
            elif args.command == "event":
                result = db.add_event(project.project_id, args.entity_id, args.type, interval(args.occurred_from, args.occurred_to), _json_value(args.effects, []), _json_value(args.evidence, []))
            elif args.command == "source":
                result = db.add_source(project.project_id, args.title, args.kind, args.uri, args.hash)
            elif args.command == "import":
                result = asdict(import_file(project, args.path, args.kind, args.title))
            elif args.command == "observation":
                result = db.add_observation(project.project_id, args.source_id, _json_value(args.observed, {}), args.entity_id, extraction=_json_value(args.extraction, {}), review_state=args.review_state)
            elif args.command == "assertion":
                result = db.add_assertion(project.project_id, args.entity_id, args.property_path, _json_value(args.value, None), interval(args.valid_from, args.valid_to), _json_value(args.uncertainty, {}), args.status, args.observation_id)
            elif args.command == "branch":
                if args.branch_command == "create":
                    result = db.create_branch(project.project_id, args.name, args.parent, args.description)
                elif args.branch_command == "list":
                    result = db.list_branches(project.project_id)
                elif args.branch_command == "diff":
                    left = db.branch_by_name(project.project_id, args.left)
                    right = db.branch_by_name(project.project_id, args.right)
                    left_items = {item["assertion_id"]: item["decision"] for item in db.list_branch_assertions(left["branch_id"])}
                    right_items = {item["assertion_id"]: item["decision"] for item in db.list_branch_assertions(right["branch_id"])}
                    result = {"left": args.left, "right": args.right, "only_left": sorted(set(left_items) - set(right_items)), "only_right": sorted(set(right_items) - set(left_items)), "changed": sorted(key for key in set(left_items) & set(right_items) if left_items[key] != right_items[key])}
                else:
                    target = db.branch_by_name(project.project_id, args.target)
                    source = db.branch_by_name(project.project_id, args.source)
                    result = db.merge_branch(target["branch_id"], source["branch_id"])
            elif args.command == "decision":
                branch = db.branch_by_name(project.project_id, args.branch)
                if args.assertion_id:
                    result = db.set_branch_assertion(branch["branch_id"], args.assertion_id, {"accept": "accepted", "reject": "rejected", "unresolved": "unresolved"}[args.action])
                    db.add_decision(project.project_id, branch["branch_id"], args.entity_id, args.assertion_id, args.action, args.rationale)
                else:
                    result = db.add_decision(project.project_id, branch["branch_id"], args.entity_id, None, args.action, args.rationale)
            elif args.command == "geometry":
                result = db.add_geometry(project.project_id, args.kind, _json_value(args.geometry, {}), metadata=_json_value(args.metadata, {}))
            elif args.command == "compile":
                scene = SceneCompiler(project).build_scene(args.time, args.branch, args.seed)
                result = {"scene": str(SceneCompiler(project).write(scene, args.output)), "root_hash": scene["root_hash"]}
            elif args.command == "export":
                compiler = SceneCompiler(project)
                if args.export_command == "project":
                    result = {"archive": str(pack_project(project.root, args.output))}
                else:
                    scene = compiler.build_scene(args.time, args.branch)
                    output = Path(args.output)
                    if args.export_command == "gltf":
                        output_path = compiler.write_gltf(scene, output)
                    elif args.export_command == "vanta":
                        output_path = compiler.export_vanta(scene, output)
                    else:
                        output.mkdir(parents=True, exist_ok=True)
                        (output / "scene.json").write_text(json.dumps(scene, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                        (output / "index.html").write_text("<!doctype html><meta charset='utf-8'><title>STRATA scene</title><pre id='scene'>Loading...</pre><script>fetch('scene.json').then(r=>r.json()).then(v=>document.querySelector('#scene').textContent=JSON.stringify(v,null,2))</script>\n", encoding="utf-8")
                        output_path = output
                    result = {"output": str(output_path), "root_hash": scene["root_hash"]}
            else:
                raise ValueError(f"unsupported command: {args.command}")
            _emit(result, args.json)
        return 0
    except Exception as exc:
        print(f"strata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
