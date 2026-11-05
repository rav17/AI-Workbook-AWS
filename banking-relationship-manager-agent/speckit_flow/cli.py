from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from speckit_flow import agents as agents_mod
from speckit_flow import audit, reviews
from speckit_flow import compose as compose_mod
from speckit_flow import custom as custom_mod
from speckit_flow import doctor as doctor_mod
from speckit_flow import knowledge as knowledge_mod
from speckit_flow import questions as questions_mod
from speckit_flow import rules as rules_mod
from speckit_flow import sensors as sensors_mod
from speckit_flow import session as session_mod
from speckit_flow import state as flow_state
from speckit_flow import trace as trace_mod
from speckit_flow.agents import DEFAULT_ROSTER_FILE
from speckit_flow.knowledge import DEFAULT_KNOWLEDGE_DIR
from speckit_flow.models import DEFAULT_PROFILE, STAGES, FeatureState, FlowError
from speckit_flow.profiles import (
    DEFAULT_PROFILES_DIR,
    get_profile,
    load_profile_file,
    load_profiles,
    suggest_profile,
)
from speckit_flow.rules import DEFAULT_RULES_FILE
from speckit_flow.sensors import DEFAULT_SENSORS_FILE

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _feature_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    pointer = _REPO_ROOT / ".specify" / "feature.json"
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        return _REPO_ROOT / str(data["feature_directory"])
    except (OSError, ValueError, KeyError) as exc:
        raise FlowError("no --feature-dir given and .specify/feature.json is unreadable") from exc


def _actor(value: str | None) -> str:
    if value:
        return value if value.startswith(("human:", "agent:")) else f"human:{value}"
    try:
        return f"human:{getpass.getuser()}"
    except Exception:
        return "human:unknown"


def _emit(args: argparse.Namespace, payload: dict[str, Any], text: str) -> None:
    print(json.dumps(payload, indent=2) if args.json else text)


def _state_summary(st: FeatureState) -> dict[str, Any]:
    return {
        "feature": st.feature,
        "profile": st.profile,
        "depth": st.depth,
        "current_stage": st.current_stage,
        "next_stage": flow_state.next_stage(st),
        "pending_gate": st.pending_gate,
        "stages": {k: v.status for k, v in st.stages.items()},
    }


def _state_text(st: FeatureState) -> str:
    return (
        f"profile={st.profile} depth={st.depth} current={st.current_stage or 'none'} "
        f"pending_gate={st.pending_gate or 'none'}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="speckit_flow")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--feature-dir")
    common.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR))
    common.add_argument("--roster-file", default=str(DEFAULT_ROSTER_FILE))
    common.add_argument("--sensors-file", default=str(DEFAULT_SENSORS_FILE))
    common.add_argument("--actor")
    common.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    prof = sub.add_parser("profiles", parents=[common])
    prof_sub = prof.add_subparsers(dest="action", required=True)
    prof_sub.add_parser("list", parents=[common])
    validate = prof_sub.add_parser("validate", parents=[common])
    validate.add_argument("id", nargs="?")
    suggest = prof_sub.add_parser("suggest", parents=[common])
    suggest.add_argument("description")

    init = sub.add_parser("init", parents=[common])
    init.add_argument("--profile", default=DEFAULT_PROFILE)
    init.add_argument("--route-file")
    switch = sub.add_parser("switch", parents=[common])
    switch.add_argument("--profile", required=True)
    switch.add_argument("--confirm", action="store_true")

    stage = sub.add_parser("stage", parents=[common])
    stage.add_argument("action", choices=["start", "done"])
    stage.add_argument("stage", choices=STAGES)
    gate = sub.add_parser("gate", parents=[common])
    gate.add_argument("action", choices=["approve", "reject"])
    gate.add_argument("stage", choices=STAGES)
    gate.add_argument("--reason", default="")
    gate.add_argument("--override-reason", default="")

    review = sub.add_parser("review", parents=[common])
    review_sub = review.add_subparsers(dest="action", required=True)
    save = review_sub.add_parser("save", parents=[common])
    save.add_argument("stage", choices=STAGES)
    save.add_argument("--file", required=True)
    rlist = review_sub.add_parser("list", parents=[common])
    rlist.add_argument("stage", nargs="?", choices=STAGES)

    rules = sub.add_parser("rules", parents=[common])
    rules_sub = rules.add_subparsers(dest="action", required=True)
    propose = rules_sub.add_parser("propose", parents=[common])
    propose.add_argument("--rules-file", default=str(DEFAULT_RULES_FILE))
    propose.add_argument("--text", required=True)
    origin = propose.add_mutually_exclusive_group(required=True)
    origin.add_argument("--from-gate", choices=STAGES)
    origin.add_argument("--from-finding")
    origin.add_argument("--manual", action="store_true")
    for verb in ("approve", "discard"):
        decide = rules_sub.add_parser(verb, parents=[common])
        decide.add_argument("--rules-file", default=str(DEFAULT_RULES_FILE))
        decide.add_argument("id")
    rules_list = rules_sub.add_parser("list", parents=[common])
    rules_list.add_argument("--rules-file", default=str(DEFAULT_RULES_FILE))
    rules_list.add_argument("--status")
    rules_list.add_argument("--stage", choices=STAGES)
    rules_list.add_argument("--effective", action="store_true")

    knowledge = sub.add_parser("knowledge", parents=[common])
    knowledge_sub = knowledge.add_subparsers(dest="action", required=True)
    klist = knowledge_sub.add_parser("list", parents=[common])
    klist.add_argument("--stage", choices=STAGES)
    klist.add_argument("--knowledge-dir", default=str(DEFAULT_KNOWLEDGE_DIR))

    compose = sub.add_parser("compose", parents=[common])
    compose_sub = compose.add_subparsers(dest="action", required=True)
    cvalidate = compose_sub.add_parser("validate", parents=[common])
    cvalidate.add_argument("--file", required=True)
    csave = compose_sub.add_parser("save", parents=[common])
    csave.add_argument("--file", required=True)
    csave.add_argument("--confirm", action="store_true")

    workflow = sub.add_parser("workflow", parents=[common])
    workflow_sub = workflow.add_subparsers(dest="action", required=True)
    begin = workflow_sub.add_parser("begin", parents=[common])
    begin.add_argument("--stages", required=True)
    begin.add_argument("--gates", required=True)

    agents = sub.add_parser("agents", parents=[common])
    agents_sub = agents.add_subparsers(dest="action", required=True)
    agents_sub.add_parser("list", parents=[common])
    agents_sub.add_parser("validate", parents=[common])
    assign = agents_sub.add_parser("assign", parents=[common])
    assign.add_argument("--profile")

    sensors = sub.add_parser("sensors", parents=[common])
    sensors_sub = sensors.add_subparsers(dest="action", required=True)
    sensors_sub.add_parser("list", parents=[common])
    srun = sensors_sub.add_parser("run", parents=[common])
    srun.add_argument("stage", choices=STAGES)
    trace_p = sub.add_parser("trace", parents=[common])
    trace_p.add_argument("--require-tests", action="store_true")
    sub.add_parser("doctor", parents=[common])
    custom_p = sub.add_parser("custom", parents=[common])
    custom_p.add_argument("action", choices=("list", "validate"))
    questions_p = sub.add_parser("questions", parents=[common])
    q_sub = questions_p.add_subparsers(dest="action", required=True)
    q_add = q_sub.add_parser("add", parents=[common])
    q_add.add_argument("text")
    q_add.add_argument("--role", required=True)
    q_answer = q_sub.add_parser("answer", parents=[common])
    q_answer.add_argument("id")
    q_answer.add_argument("text")
    q_list = q_sub.add_parser("list", parents=[common])
    q_list.add_argument("--open", action="store_true")
    q_list.add_argument("--role")
    q_sub.add_parser("check", parents=[common])
    intents = sub.add_parser("intents", parents=[common])
    intents_sub = intents.add_subparsers(dest="action", required=True)
    intents_sub.add_parser("list", parents=[common])
    iswitch = intents_sub.add_parser("switch", parents=[common])
    iswitch.add_argument("name")
    ipark = intents_sub.add_parser("park", parents=[common])
    ipark.add_argument("--reason", default="")
    intents_sub.add_parser("unpark", parents=[common])
    for verb in ("redo", "jump"):
        rework = sub.add_parser(verb, parents=[common])
        rework.add_argument("stage", choices=STAGES)
        rework.add_argument("--reason", required=True)

    for name in ("status", "resume"):
        sub.add_parser(name, parents=[common])
    rebuild = sub.add_parser("rebuild", parents=[common])
    rebuild.add_argument("--profile")
    return parser


def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"cannot read {path}: {exc}") from exc


def _parse_route_arg(value: str, label: str, allow_empty: bool = False) -> list[str]:
    if not value and allow_empty:
        return []
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(not part for part in parts):
        raise FlowError(f"{label} must be a comma-separated list without empty entries")
    return parts


def _run_review(args: argparse.Namespace, feature_dir: Path, actor: str) -> int:
    if args.action == "save":
        payload = _read_json(args.file)
        if not isinstance(payload, dict):
            raise FlowError("review file must be a JSON object")
        saved = reviews.save_review(feature_dir, args.stage, payload, actor)
        _emit(args, saved.to_dict(), f"saved review {saved.id} verdict={saved.verdict}")
        return 0
    items = [
        {**r.to_dict(), "stale": reviews.is_stale(feature_dir, r)}
        for r in reviews.list_reviews(feature_dir, args.stage)
    ]
    text = "\n".join(
        f"{i['id']:14} {i['verdict']:9} findings={len(i['findings'])}"
        f"{' STALE' if i['stale'] else ''}"
        for i in items
    )
    _emit(args, {"reviews": items}, text or "no reviews found")
    return 0


def _run_rules(args: argparse.Namespace, actor: str) -> int:
    path = Path(args.rules_file)
    if args.action == "list":
        if args.effective:
            result = rules_mod.effective_rules(path, args.stage)
        else:
            result = rules_mod.list_rules(path, args.status, args.stage)
        lines = [
            f"{r['id']} [{r.get('layer', r['status'])}]"
            f"{' CONFLICT' if r['conflict'] else ''} {r['text']}"
            for r in result["rules"]
        ]
        if result["omitted"]:
            lines.append(f"({result['omitted']} older active rule(s) omitted)")
        _emit(args, result, "\n".join(lines) or "no rules found")
        return 0
    feature_dir = _feature_dir(args.feature_dir)
    if args.action == "propose":
        rule = rules_mod.propose_rule(
            feature_dir,
            args.text,
            actor,
            from_gate=args.from_gate,
            from_finding=args.from_finding,
            path=path,
        )
    else:
        rule = rules_mod.decide_rule(feature_dir, args.id, args.action == "approve", actor, path)
    _emit(args, rule.to_dict(), f"{rule.id} is {rule.status}")
    return 0


def _run_compose(args: argparse.Namespace, actor: str) -> int:
    feature_dir = _feature_dir(args.feature_dir)
    route = compose_mod.load_route_file(Path(args.file), feature_dir.name)
    if args.action == "validate":
        _emit(args, {"valid": route.profile.id}, f"route {route.profile.id} is valid")
        return 0
    st = compose_mod.save_route(feature_dir, route, actor, args.confirm)
    _emit(args, _state_summary(st), _state_text(st))
    return 0


def _run_agents(args: argparse.Namespace, profiles_dir: Path) -> int:
    roster = agents_mod.load_roster(Path(args.roster_file))
    if args.action == "list":
        _emit(
            args,
            {"agents": [a.to_dict() for a in roster.values()]},
            "\n".join(
                f"{a.id:22} {a.role:9} {a.tier:9} leads={','.join(a.leads) or '-'} "
                f"supports={','.join(a.supports) or '-'}"
                for a in roster.values()
            ),
        )
        return 0
    if args.action == "validate":
        problems = agents_mod.validate_roster(roster, _REPO_ROOT)
        if problems:
            raise FlowError("roster invalid: " + "; ".join(problems))
        counts = {r: sum(1 for a in roster.values() if a.role == r) for r in agents_mod.ROLES}
        _emit(
            args,
            {"valid": True, "counts": counts},
            f"roster valid: {counts['domain']} domain, {counts['reviewer']} reviewer, "
            f"{counts['composer']} composer, {counts['conductor']} conductor",
        )
        return 0
    if args.profile:
        profile = get_profile(args.profile, profiles_dir)
    else:
        feature_dir = _feature_dir(args.feature_dir)
        profile = flow_state.profile_for(
            feature_dir, flow_state.load_state(feature_dir).profile, profiles_dir
        )
    assignments = agents_mod.resolve_assignments(profile, roster)
    _emit(
        args,
        {"profile": profile.id, "assignments": assignments},
        "\n".join(
            f"{stage:10} lead={entry['lead']} support={','.join(entry['support']) or '-'}"
            for stage, entry in assignments.items()
        ),
    )
    return 0


def _check_agent_actor(args: argparse.Namespace, actor: str) -> None:
    path = Path(args.roster_file)
    if actor.startswith("agent:") and path.is_file():
        agents_mod.check_actor(actor, agents_mod.load_roster(path))


def _run_sensors(args: argparse.Namespace, actor: str) -> int:
    path = Path(args.sensors_file)
    if args.action == "list":
        listed = sensors_mod.load_sensors(path)
        _emit(
            args,
            {"sensors": [s.to_dict() for s in listed]},
            "\n".join(
                f"{s.id:20} {s.kind:8} required={s.required} stages={','.join(s.stages)}"
                for s in listed
            ),
        )
        return 0
    outcomes = sensors_mod.run_stage(_feature_dir(args.feature_dir), args.stage, actor, path)
    _emit(
        args,
        {"stage": args.stage, "results": outcomes},
        "\n".join(f"{o['status']:4} {o['id']}: {o['reason']}" for o in outcomes)
        or f"no sensors configured for {args.stage}",
    )
    return 0 if all(o["status"] == "pass" for o in outcomes) else 1


def _run_trace(args: argparse.Namespace) -> int:
    matrix = trace_mod.build_matrix(_feature_dir(args.feature_dir))
    _emit(args, matrix.to_dict(), trace_mod.render(matrix))
    return 0 if matrix.ok(args.require_tests) else 1


def _run_intents(args: argparse.Namespace, actor: str) -> int:
    if args.action == "list":
        items = session_mod.list_intents(_REPO_ROOT)
        _emit(
            args,
            {"intents": [i.to_dict() for i in items]},
            "\n".join(i.line() for i in items) or "no initialized features",
        )
        return 0
    if args.action == "switch":
        feature_dir = session_mod.switch_intent(_REPO_ROOT, args.name, actor)
        note = " (parked; run 'intents unpark')" if audit.is_parked(feature_dir) else ""
        _emit(args, {"active": args.name}, f"active feature: {args.name}{note}")
        return 0
    feature_dir = _feature_dir(args.feature_dir)
    if args.action == "park":
        session_mod.park(feature_dir, actor, args.reason)
    else:
        session_mod.unpark(feature_dir, actor)
    _emit(args, {"parked": args.action == "park"}, f"{feature_dir.name}: {args.action}ed")
    return 0


def _run_questions(args: argparse.Namespace, actor: str) -> int:
    feature_dir = _feature_dir(args.feature_dir)
    if args.action == "add":
        roles: set[str] | None = None
        roster_path = Path(args.roster_file)
        if roster_path.is_file():
            roles = set(agents_mod.load_roster(roster_path))
        question = questions_mod.add_question(feature_dir, args.text, args.role, actor, roles)
        _emit(args, question.to_dict(), f"{question.id} asked of {question.role}")
    elif args.action == "answer":
        question = questions_mod.answer_question(feature_dir, args.id, args.text, actor)
        _emit(args, question.to_dict(), f"{question.id} answered")
    elif args.action == "list":
        result = questions_mod.list_questions(feature_dir, args.open, args.role)
        lines = [f"{q['id']} [{q['role']}] {q['status']}: {q['text']}" for q in result["questions"]]
        _emit(args, result, "\n".join(lines) or "no questions")
    else:
        pending = questions_mod.open_questions(feature_dir)
        _emit(
            args,
            {"open": [q.id for q in pending]},
            f"{len(pending)} open question(s)" + "".join(f"\n{q.id} [{q.role}]" for q in pending),
        )
        return 1 if pending else 0
    return 0


def _run_custom(args: argparse.Namespace) -> int:
    profiles_dir, sensors_file = Path(args.profiles_dir), Path(args.sensors_file)
    if args.action == "list":
        result = custom_mod.describe(profiles_dir, sensors_file)
        lines = [f"{i['type']} {i['id']} ({i['effect']})" for i in result["items"]]
        _emit(args, result, "\n".join(lines) or "no custom overlay")
    else:
        result = custom_mod.validate(profiles_dir, sensors_file)
        _emit(args, result, f"custom overlay valid: {result['profiles']} profile(s) merged")
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    try:
        feature_dir: Path | None = _feature_dir(args.feature_dir)
    except FlowError:
        feature_dir = None
    checks = doctor_mod.run_doctor(
        _REPO_ROOT,
        Path(args.profiles_dir),
        Path(args.roster_file),
        Path(args.sensors_file),
        DEFAULT_RULES_FILE,
        feature_dir,
    )
    _emit(args, {"checks": [c.to_dict() for c in checks]}, doctor_mod.render(checks))
    return 1 if any(c.status == "fail" for c in checks) else 0


def _status_payload(
    args: argparse.Namespace, st: FeatureState, feature_dir: Path, profiles_dir: Path
) -> tuple[dict[str, Any], str]:
    payload = _state_summary(st)
    text = _state_text(st)
    stage = st.current_stage or flow_state.next_stage(st)
    try:
        roster = agents_mod.load_roster(Path(args.roster_file))
        profile = flow_state.profile_for(feature_dir, st.profile, profiles_dir)
        lead = agents_mod.resolve_assignments(profile, roster).get(stage or "", {}).get("lead")
    except FlowError:
        lead = None
    if lead:
        payload["lead_agent"] = lead
        text += f" lead_agent={lead}"
    return payload, text


def _run(args: argparse.Namespace) -> int:
    profiles_dir = Path(args.profiles_dir)
    actor = _actor(args.actor)
    _check_agent_actor(args, actor)

    if args.command == "agents":
        return _run_agents(args, profiles_dir)
    if args.command == "sensors":
        return _run_sensors(args, actor)
    if args.command == "trace":
        return _run_trace(args)
    if args.command == "questions":
        return _run_questions(args, actor)
    if args.command == "custom":
        return _run_custom(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "intents":
        return _run_intents(args, actor)
    if args.command in ("redo", "jump"):
        st = session_mod.redo_stage(_feature_dir(args.feature_dir), args.stage, actor, args.reason)
        _emit(args, _state_summary(st), _state_text(st))
        return 0
    if args.command == "knowledge":
        docs = knowledge_mod.list_knowledge(args.stage, Path(args.knowledge_dir))
        _emit(
            args,
            {"knowledge": [vars(d) | {"stages": list(d.stages)} for d in docs]},
            "\n".join(f"{d.title} ({d.path})" for d in docs) or "no knowledge found",
        )
        return 0
    if args.command == "rules":
        return _run_rules(args, actor)
    if args.command == "compose":
        return _run_compose(args, actor)
    if args.command == "workflow":
        feature_dir = _feature_dir(args.feature_dir)
        st = flow_state.begin_workflow(
            feature_dir,
            _parse_route_arg(args.stages, "workflow stages"),
            _parse_route_arg(args.gates, "workflow gates", allow_empty=True),
            actor,
            profiles_dir,
        )
        _emit(args, _state_summary(st), _state_text(st))
        return 0
    if args.command == "profiles":
        if args.action == "list":
            profiles = load_profiles(profiles_dir)
            _emit(
                args,
                {k: v.to_dict() for k, v in profiles.items()},
                "\n".join(
                    f"{p.id:15} {p.depth:14} {' > '.join(p.stages)}  "
                    f"gates: {', '.join(p.gates) or '-'}"
                    for p in profiles.values()
                ),
            )
        elif args.action == "validate":
            paths = (
                [profiles_dir / f"{args.id}.json"]
                if args.id
                else sorted(profiles_dir.glob("*.json"))
            )
            if not paths:
                raise FlowError(f"no profiles found in {profiles_dir}")
            for path in paths:
                load_profile_file(path)
            _emit(args, {"valid": [p.stem for p in paths]}, f"{len(paths)} profile(s) valid")
        else:
            available = set(load_profiles(profiles_dir))
            pid, why = suggest_profile(args.description, available)
            _emit(args, {"profile": pid, "reason": why}, f"{pid} ({why})")
        return 0

    feature_dir = _feature_dir(args.feature_dir)
    if args.command == "review":
        return _run_review(args, feature_dir, actor)
    if args.command == "init":
        if args.route_file:
            route = compose_mod.load_route_file(Path(args.route_file), feature_dir.name)
            st = compose_mod.save_route(feature_dir, route, actor, confirm=True)
        else:
            st = flow_state.init_state(feature_dir, args.profile, actor, profiles_dir)
    elif args.command == "switch":
        st = flow_state.switch_profile(feature_dir, args.profile, actor, args.confirm, profiles_dir)
    elif args.command == "stage":
        if args.action == "start":
            st = flow_state.start_stage(feature_dir, args.stage, actor)
        else:
            st = flow_state.done_stage(feature_dir, args.stage, actor, profiles_dir)
    elif args.command == "gate":
        sensors_path = Path(args.sensors_file)
        st = flow_state.decide_gate(
            feature_dir,
            args.stage,
            args.action == "approve",
            actor,
            args.reason,
            args.override_reason,
            sensors_path if sensors_path.is_file() else None,
            profiles_dir,
        )
    elif args.command == "rebuild":
        st = flow_state.rebuild_state(feature_dir, actor, args.profile, profiles_dir)
    else:
        try:
            st = flow_state.load_state(feature_dir)
        except FlowError as exc:
            raise FlowError(
                f"{exc}; run 'rebuild' to reconstruct it from existing artifacts"
            ) from exc
        broken = audit.verify_chain(feature_dir)
        if broken:
            raise FlowError(f"audit trail integrity problem: {broken}")
        payload, text = _status_payload(args, st, feature_dir, profiles_dir)
        _emit(args, payload, text)
        return 0
    _emit(args, _state_summary(st), _state_text(st))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _run(args)
    except FlowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
