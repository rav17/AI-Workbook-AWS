from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from speckit_flow import agents as agents_mod
from speckit_flow import assurance as assurance_mod
from speckit_flow import audit, reviews
from speckit_flow import calls as calls_mod
from speckit_flow import codebase as codebase_mod
from speckit_flow import compose as compose_mod
from speckit_flow import contracts as contracts_mod
from speckit_flow import custom as custom_mod
from speckit_flow import diagrams as diagrams_mod
from speckit_flow import doctor as doctor_mod
from speckit_flow import knowledge as knowledge_mod
from speckit_flow import orchestration as orchestration_mod
from speckit_flow import plugins as plugins_mod
from speckit_flow import profiles as profiles_mod
from speckit_flow import questions as questions_mod
from speckit_flow import recovery as recovery_mod
from speckit_flow import rules as rules_mod
from speckit_flow import sensors as sensors_mod
from speckit_flow import session as session_mod
from speckit_flow import state as flow_state
from speckit_flow import trace as trace_mod
from speckit_flow import units as units_mod
from speckit_flow.agents import DEFAULT_ROSTER_FILE
from speckit_flow.knowledge import DEFAULT_KNOWLEDGE_DIR
from speckit_flow.models import (
    DEFAULT_PROFILE,
    STAGE_DEFS,
    STAGES,
    FeatureState,
    FlowError,
    ReviewSelectionError,
)
from speckit_flow.profiles import (
    DEFAULT_PROFILES_DIR,
    get_profile,
    load_profile_file,
    load_profiles,
    suggest_profile,
)
from speckit_flow.rules import DEFAULT_RULES_FILE
from speckit_flow.sensors import DEFAULT_SENSORS_FILE
from speckit_flow.stagedefs import load_stage_defs

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


def _review_status_text(status: dict[str, Any]) -> str:
    labels = {
        "review_current": "successful review",
        "no_review": "no review",
        "reviewer_unavailable": "reviewer unavailable",
        "stale_review": "stale review",
        "invalid_incomplete_review": "invalid or incomplete review",
        "missing_reviewer_selection": "missing reviewer selection",
        "invalid_reviewer_selection": "invalid reviewer selection",
        "missing_input_evidence": "missing review input-boundary evidence",
        "unverified_input_evidence": "unverified review input boundary",
        "inconsistent_input_evidence": "inconsistent review input boundary",
    }
    state = status["state"]
    label = labels.get(state)
    lines = [
        f"Review state: {state}" + (f" - {label}" if label else ""),
        f"Invocation outcome: {status.get('invocation_outcome', 'not_recorded')}",
        f"Verdict: {status.get('verdict', 'not_available')}",
        f"Freshness: {status.get('freshness', 'not_verified')}",
        f"Reason: {status['reason']}",
        f"Next action: {status['next_action']}",
    ]
    for finding in status.get("findings", []):
        lines.append(
            f"Finding: {finding['severity']} in {finding['file']}, "
            f"{finding['section']}: {finding['note']}"
        )
    return "\n".join(lines)


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
    common.add_argument("--verify-file", default=str(units_mod.DEFAULT_VERIFY_FILE))
    common.add_argument("--actor")
    common.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    codebase = sub.add_parser("codebase", parents=[common])
    codebase.add_argument("action", choices=["scan", "practices"])
    codebase.add_argument("--project-dir", help="Project/package root (defaults to toolkit root)")

    diagrams = sub.add_parser("diagrams", parents=[common])
    diagrams_sub = diagrams.add_subparsers(dest="action", required=True)
    diagrams_sub.add_parser("validate", parents=[common])

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
    init.add_argument("--reviewer")
    init.add_argument("--confirm-route", action="store_true")
    init.add_argument("--reviewer-rationale", default="")
    init.add_argument("--route-rationale", default="")
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
    save.add_argument("--host-call-id", default="")
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
    recommend = workflow_sub.add_parser("recommend", parents=[common])
    recommend.add_argument("description")
    recommend.add_argument("--profile")
    dispatch = workflow_sub.add_parser("dispatch", parents=[common])
    dispatch.add_argument("--stage", choices=STAGES)
    workflow_sub.add_parser("next", parents=[common])
    assurance = workflow_sub.add_parser("assurance", parents=[common])
    assurance_sub = assurance.add_subparsers(dest="assurance_action", required=True)
    for action in ("accept", "status"):
        operation = assurance_sub.add_parser(action, parents=[common])
        operation.add_argument("--stage", choices=STAGES, required=True)
        operation.add_argument("--host", required=True)
        operation.add_argument("--session-id", required=True)
        if action == "accept":
            operation.add_argument("--reason", required=True)
            operation.add_argument("--observation", required=True)
            operation.add_argument("--confirm-ordinary-work", action="store_true")
    recovery = workflow_sub.add_parser("recovery", parents=[common])
    recovery.add_argument("--timeout-seconds", type=float)
    recovery.add_argument("--approval-package", action="store_true")
    recovery.add_argument("--expected-fingerprint")
    host_consent = workflow_sub.add_parser("host-consent", parents=[common])
    host_consent.add_argument("--events-file", required=True)
    host_consent.add_argument("--session-id", required=True)
    host_evidence = workflow_sub.add_parser("host-evidence", parents=[common])
    host_evidence.add_argument("--events-file", required=True)
    host_evidence.add_argument("--session-id", default="")
    host_capability = workflow_sub.add_parser("host-capability", parents=[common])
    host_capability.add_argument("--call-id", required=True)
    review_result = workflow_sub.add_parser("review-result", parents=[common])
    review_result.add_argument("--reservation-id", type=int, required=True)
    review_result.add_argument("--call-id", required=True)
    calls = workflow_sub.add_parser("calls", parents=[common])
    call_sub = calls.add_subparsers(dest="call_action", required=True)
    for action in ("reserve", "finish", "reset", "status", "inline"):
        call = call_sub.add_parser(action, parents=[common])
        call.add_argument("--stage", choices=STAGES, required=True)
        if action == "reserve":
            call.add_argument("agent_id")
        elif action == "finish":
            call.add_argument("call_id", type=int)
            call.add_argument("--outcome", choices=("succeeded", "failed"), required=True)
        elif action == "reset":
            call.add_argument("--reason", required=True)

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
    contracts = sub.add_parser("contracts", parents=[common])
    contracts_sub = contracts.add_subparsers(dest="action", required=True)
    contracts_sub.add_parser("list", parents=[common])
    contract_show = contracts_sub.add_parser("show", parents=[common])
    contract_show.add_argument("stage", choices=STAGES)
    trace_p = sub.add_parser("trace", parents=[common])
    trace_p.add_argument("--require-tests", action="store_true")
    sub.add_parser("doctor", parents=[common])
    sub.add_parser("stages", parents=[common])
    plugins_p = sub.add_parser("plugins", parents=[common])
    plugins_p.add_argument("action", choices=("list", "validate"))
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
    units_p = sub.add_parser("units", parents=[common])
    u_sub = units_p.add_subparsers(dest="action", required=True)
    u_add = u_sub.add_parser("add", parents=[common])
    u_add.add_argument("id")
    u_add.add_argument("title")
    u_add.add_argument("--depends-on", default="")
    u_add.add_argument("--tasks", default="")
    u_add.add_argument("--files", default="")
    u_sub.add_parser("list", parents=[common])
    u_cp = u_sub.add_parser("checkpoint", parents=[common])
    u_cp.add_argument("id")
    verify_p = sub.add_parser("verify", parents=[common])
    v_sub = verify_p.add_subparsers(dest="action", required=True)
    v_prop = v_sub.add_parser("propose", parents=[common])
    v_prop.add_argument("argv", nargs="+")
    v_sub.add_parser("approve", parents=[common])
    v_sub.add_parser("show", parents=[common])
    v_sub.add_parser("run", parents=[common])
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

    for name in ("status", "resume", "context"):
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
        saved = reviews.save_review(
            feature_dir, args.stage, payload, actor, host_call_id=args.host_call_id,
        )
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


def _require_ceremony(feature_dir: Path, name: str, profiles_dir: Path) -> None:
    """Refuse an optional ceremony the feature's profile switches off; no state means allowed."""
    if not (feature_dir / flow_state.STATE_FILE).is_file():
        return
    st = flow_state.load_state(feature_dir)
    profile = flow_state.profile_for(feature_dir, st.profile, profiles_dir)
    if not profile.ceremony_on(name):
        raise FlowError(f"profile {profile.id} switches off ceremony {name!r}")


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
        _require_ceremony(feature_dir, "learning", Path(args.profiles_dir))
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


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _run_units(args: argparse.Namespace, actor: str) -> int:
    feature_dir = _feature_dir(args.feature_dir)
    if args.action == "add":
        unit = units_mod.add_unit(
            feature_dir, args.id, args.title, _csv(args.depends_on), _csv(args.tasks), actor,
            files=_csv(args.files),
        )
        _emit(args, unit, f"unit {unit['id']} defined")
    elif args.action == "list":
        result = units_mod.list_units(feature_dir, Path(args.verify_file))
        lines = [
            f"{u['id']} [{u['status']}] {u['title']} coverage={u['coverage']}"
            f" (after: {', '.join(u['depends_on']) or '-'}): "
            f"{'; '.join(u['reasons']) or 'current checkpoint'}"
            for u in result["units"]
        ]
        _emit(args, result, ("\n".join(lines) or "no units") + "\n" + result["notice"])
    else:
        ok, note = units_mod.checkpoint_unit(feature_dir, args.id, actor, Path(args.verify_file))
        _emit(args, {"unit": args.id, "passed": ok, "note": note}, f"{args.id}: {note}")
        return 0 if ok else 1
    return 0


def _run_verify(args: argparse.Namespace, actor: str) -> int:
    path = Path(args.verify_file)
    if args.action == "propose":
        data = units_mod.propose_verify(list(args.argv), actor, path)
        _emit(args, data, "proposed; a human must run 'verify approve'")
    elif args.action == "approve":
        data = units_mod.approve_verify(actor, path)
        _emit(args, data, f"approved by {actor}")
    elif args.action == "show":
        data = units_mod.load_verify(path) or {}
        _emit(args, data, " ".join(data.get("command", [])) or "no verification command")
    else:
        ok, note, _ = units_mod.run_verify(_REPO_ROOT, path)
        _emit(args, {"passed": ok, "note": note}, note)
        return 0 if ok else 1
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


def _run_plugins(args: argparse.Namespace) -> int:
    specify_dir = Path(args.profiles_dir).parent
    try:
        found = plugins_mod.discover(specify_dir, enabled_only=False)
    except plugins_mod.PluginError as exc:
        raise FlowError(str(exc)) from exc
    items: list[dict[str, Any]] = [
        {
            "name": p.name,
            "version": p.version,
            "enabled": p.enabled,
            "provides": [
                kind
                for kind, present in (
                    ("profiles", p.profiles_dir.is_dir()),
                    ("sensors", p.sensors_file.is_file()),
                    ("stages", p.stages_file.is_file()),
                    ("contracts", p.contracts_dir.is_dir()),
                )
                if present
            ],
        }
        for p in found
    ]
    if args.action == "validate":
        profiles_mod.load_profiles(Path(args.profiles_dir))
        sensors_mod.load_sensors(Path(args.sensors_file))
        load_stage_defs()
    lines = [
        f"{i['name']} {i['version']} {'on' if i['enabled'] else 'off'} "
        f"[{', '.join(i['provides']) or 'nothing'}]"
        for i in items
    ]
    _emit(args, {"plugins": items}, "\n".join(lines) or "no plugins")
    return 0


def _run_stages(args: argparse.Namespace) -> int:
    items = [
        {
            "id": d.id,
            "phase": d.phase,
            "optional": d.optional,
            "requires": list(d.requires),
            "lead": d.lead,
            "custom": d.custom,
            "condition": d.condition,
        }
        for d in STAGE_DEFS
    ]
    lines = [
        f"{i['id']} [{i['phase']}]{' optional' if i['optional'] else ''}"
        f"{' custom' if i['custom'] else ''}"
        for i in items
    ]
    _emit(args, {"stages": items}, "\n".join(lines))
    return 0


def _run_contracts(args: argparse.Namespace) -> int:
    specify_dir = Path(args.profiles_dir).parent
    available = contracts_mod.load_contracts(specify_dir)
    selected = available
    active_profile: str | None = None
    if args.feature_dir:
        feature_dir = _feature_dir(args.feature_dir)
        state = flow_state.load_state(feature_dir)
        profile = flow_state.profile_for(feature_dir, state.profile, Path(args.profiles_dir))
        if not profile.stage_contracts:
            raise FlowError(f"profile {profile.id!r} does not enable stage contracts")
        active_profile = profile.id
        missing = [stage for stage in profile.stages if stage not in available]
        if missing:
            raise FlowError(
                f"profile {profile.id}: missing contracts for routed stages: "
                f"{', '.join(missing)}"
            )
        selected = {stage: available[stage] for stage in profile.stages}
    if args.action == "show":
        contract = selected.get(args.stage)
        if contract is None:
            raise FlowError(f"no stage contract found for {args.stage!r}")
        items = [contract.to_dict()]
    else:
        items = [selected[stage].to_dict() for stage in sorted(selected)]
    if args.json:
        _emit(
            args,
            {"profile": active_profile, "contracts": items},
            "",
        )
    else:
        lines: list[str] = []
        for item in items:
            lines.extend(
                [
                    f"{item['stage']}: {item['purpose']}",
                    f"  Inputs: {', '.join(value['id'] for value in item['inputs']) or 'none'}",
                    f"  Outputs: {', '.join(value['id'] for value in item['outputs']) or 'none'}",
                    f"  Acceptance: {'; '.join(item['acceptance_criteria'])}",
                ]
            )
        _emit(args, {"profile": active_profile, "contracts": items}, "\n".join(lines))
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
    if args.command == "contracts":
        return _run_contracts(args)
    if args.command == "trace":
        return _run_trace(args)
    if args.command == "questions":
        return _run_questions(args, actor)
    if args.command == "units":
        return _run_units(args, actor)
    if args.command == "verify":
        return _run_verify(args, actor)
    if args.command == "plugins":
        return _run_plugins(args)
    if args.command == "stages":
        return _run_stages(args)
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
        if args.action == "recommend":
            result = orchestration_mod.recommend(
                args.description, load_profiles(profiles_dir), args.profile
            )
            _emit(
                args, result,
                f"{result['profile'] or 'ask user'}: {result['reason']} "
                "(confirmation required)",
            )
            return 0
        feature_dir = _feature_dir(args.feature_dir)
        if args.action == "assurance":
            options = {
                "profiles_dir": profiles_dir, "roster_file": Path(args.roster_file),
                "root": _REPO_ROOT,
            }
            if args.assurance_action == "accept":
                if args.actor is None:
                    raise FlowError("acceptance requires an explicit human actor")
                result = assurance_mod.accept(
                    feature_dir, args.stage, args.host, args.session_id, actor,
                    args.reason, args.observation, args.confirm_ordinary_work, **options,
                )
            else:
                result = assurance_mod.status(
                    feature_dir, args.stage, args.host, args.session_id, **options,
                )
            tools = "\n".join(
                f"Declared tools for {name}: {', '.join(names) or '(none)'}"
                for name, names in result.get("declared_tools", {}).items()
            )
            _emit(
                args, result,
                f"{result['status']}: {result['reason']}\n"
                f"Feature/stage: {result['feature']} / {result['stage']}\n"
                f"Attested context: {result['host']} / {result['session_id']}\n"
                f"Runtime enforcement: {result['runtime_enforcement']}\n"
                f"Missing evidence: {result['missing_evidence']}\n"
                f"Residual risk: {result['residual_risk']}\n"
                f"Acceptance event: {result['acceptance_event']}\n{tools}",
            )
            return 0 if result["status"] == "unverified_accepted" else 1
        if args.action == "next":
            result = orchestration_mod.next_action(
                feature_dir, profiles_dir=profiles_dir,
                roster_file=Path(args.roster_file), root=_REPO_ROOT,
                sensors_file=Path(args.sensors_file),
            )
            detail = f"{result['action']}: {result['reason']}\nNext action: {result['next_action']}"
            readiness = result.get("readiness")
            if readiness is not None:
                detail += f"\nExecution: {result['execution_choice']} ({result['execution']})"
                detail += f"\nOpen questions: {readiness['questions']['open_count']}"
                detail += (
                    f"\nSensor configuration: {readiness['sensor_config']} (not a test result)"
                )
                for artifact in readiness["artifacts"]:
                    detail += f"\nArtifact {artifact['path']}: " + (
                        "present (not validated)" if artifact["present"] else "missing"
                    )
                for sensor in readiness["sensors"]:
                    detail += f"\nCheck {sensor['id']}: {sensor['status']} - {sensor['reason']}"
                detail += "\n" + readiness["notice"]
            if "delegation_assurance" in result.get("dispatch", {}):
                assurance_status = result["dispatch"]["delegation_assurance"]
                detail += (
                    f"\nDelegation assurance: {assurance_status['status']}; "
                    f"runtime enforcement unverified. {assurance_status['reason']}"
                )
            if "approval_package" in result:
                detail += "\nApproval package required: " + ", ".join(
                    result["approval_package"]["required_sections"]
                )
            _emit(args, result, detail)
            return 1 if result["action"] == "blocked" else 0
        if args.action == "recovery":
            if args.expected_fingerprint is not None and not args.approval_package:
                raise FlowError("--expected-fingerprint requires --approval-package")
            result = (
                recovery_mod.bounded_status(
                    feature_dir, args.timeout_seconds, profiles_dir=profiles_dir,
                    include_evidence=args.approval_package,
                )
                if args.timeout_seconds is not None
                else recovery_mod.status(
                    feature_dir, profiles_dir=profiles_dir, include_evidence=args.approval_package,
                )
            )
            detail = (
                f"{result['status']}: {result['reason']}\n"
                f"Verified units: {', '.join(result['verified_units']) or 'none'}\n"
                f"Uncertain units: {', '.join(result['uncertain_units']) or 'none'}\n"
                f"Resume allowed: {result['resume_allowed']}\n"
                f"Ownership transfer allowed: False\nNext action: {result['next_action']}\n"
                f"{result['notice']}"
            )
            if args.approval_package:
                result["approval_package"] = recovery_mod.decision_package(
                    result, args.expected_fingerprint,
                )
                del result["checkpoint_inventory"]
                del result["evidence_snapshot"]
                detail += "\n\n" + recovery_mod.decision_package_text(result["approval_package"])
            _emit(args, result, detail)
            if args.expected_fingerprint is not None and (
                result["approval_package"]["evidence_snapshot"]["comparison"] != "unchanged"
            ):
                return 1
            return 1 if result["status"] in ("unknown", "unavailable") else 0
        if args.action in ("host-consent", "host-evidence"):
            from speckit_flow import host

            if args.action == "host-consent":
                host.authorize_source(feature_dir, Path(args.events_file), actor, args.session_id)
                _emit(
                    args,
                    {"status": "consent_recorded"},
                    "host source consent recorded; log not read",
                )
            else:
                host.configure(feature_dir, Path(args.events_file), actor, args.session_id)
                _emit(args, {"status": "configured"}, "host evidence source configured")
            return 0
        if args.action == "review-result":
            from speckit_flow import host

            result = host.complete_review(
                feature_dir, args.reservation_id, args.call_id, actor
            )
            _emit(args, result, json.dumps(result))
            return 0
        if args.action == "host-capability":
            from speckit_flow import agents, host

            hybrid_route = flow_state.load_hybrid_route(feature_dir)
            reviewer = agents.load_roster(Path(args.roster_file)).get(hybrid_route["reviewer"])
            if reviewer is None:
                raise FlowError("selected reviewer is unavailable")
            host.verify_capability(feature_dir, args.call_id, reviewer.agent_name, actor)
            _emit(args, {"status": "verified"}, "no-tool host capability evidence recorded")
            return 0
        if args.action == "calls":
            if args.call_action == "inline":
                calls_mod.record_inline(feature_dir, args.stage, actor, profiles_dir)
                result = {"status": "inline_recorded", "stage": args.stage}
            elif args.call_action == "reserve":
                result = calls_mod.reserve(
                    feature_dir, args.stage, args.agent_id, actor,
                    profiles_dir=profiles_dir, roster_file=Path(args.roster_file), root=_REPO_ROOT,
                )
            elif args.call_action == "finish":
                calls_mod.finish(feature_dir, args.stage, args.call_id, args.outcome, actor)
                result = {"id": args.call_id, "status": args.outcome}
            elif args.call_action == "reset":
                calls_mod.reset(feature_dir, args.stage, actor, args.reason)
                result = {"status": "reset", "stage": args.stage}
            else:
                result = {"calls": calls_mod.status(feature_dir, args.stage)}
            _emit(args, result, json.dumps(result))
            return 0
        if args.action == "dispatch":
            result = orchestration_mod.dispatch(
                feature_dir, args.stage, profiles_dir=profiles_dir,
                roster_file=Path(args.roster_file), root=_REPO_ROOT,
            )
            blocked = result["status"] == "blocked"
            status = result.get("review_status")
            detail = ""
            if status is not None:
                detail = "\n" + _review_status_text(status)
            assurance_status = result.get("delegation_assurance")
            if assurance_status is not None:
                detail += (
                    f"\nDelegation assurance: {assurance_status['status']}; "
                    f"runtime enforcement unverified. {assurance_status['reason']}"
                )
            _emit(
                args, result,
                f"{result['status']}: profile={result['profile']} "
                f"stage={result.get('stage', 'none')} "
                f"lead={result.get('lead', {}).get('agent_name', 'none')}{detail}",
            )
            return 1 if blocked else 0
        st = flow_state.begin_workflow(
            feature_dir,
            _parse_route_arg(args.stages, "workflow stages"),
            _parse_route_arg(args.gates, "workflow gates", allow_empty=True),
            actor,
            profiles_dir,
        )
        _emit(args, _state_summary(st), _state_text(st))
        return 0
    if args.command == "codebase":
        root = Path(args.project_dir) if args.project_dir else _REPO_ROOT
        if args.action == "practices":
            payload = codebase_mod.practices(root)
            text = "\n".join([
                f"Practices sources: {payload['status']} fingerprint={payload['fingerprint']}",
                *(f"{source['path']} sha256={source['sha256']}" for source in payload["sources"]),
                payload["notice"],
            ])
            _emit(args, payload, text)
            return 0
        inventory = codebase_mod.scan(root)
        _emit(args, inventory.to_dict(), inventory.markdown())
        return 0
    if args.command == "diagrams":
        payload, text = diagrams_mod.validate(_feature_dir(args.feature_dir))
        _emit(args, payload, text)
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
        if args.route_rationale and args.reviewer_rationale:
            raise FlowError("choose either --route-rationale or --reviewer-rationale")
        if args.route_file:
            if (
                args.reviewer is not None or args.confirm_route
                or args.reviewer_rationale or args.route_rationale
            ):
                raise FlowError("reviewer selection cannot be combined with --route-file")
            route = compose_mod.load_route_file(Path(args.route_file), feature_dir.name)
            st = compose_mod.save_route(feature_dir, route, actor, confirm=True)
        else:
            try:
                st = flow_state.init_state(
                    feature_dir,
                    args.profile,
                    actor,
                    profiles_dir,
                    reviewer=args.reviewer,
                    confirm_route=args.confirm_route,
                    rationale=args.route_rationale or args.reviewer_rationale,
                    roster_file=Path(args.roster_file),
                )
            except ReviewSelectionError as exc:
                status = {
                    "state": exc.state,
                    "invocation_outcome": "not_recorded",
                    "verdict": "not_available",
                    "freshness": "not_verified",
                    "reason": exc.reason,
                    "next_action": exc.next_action,
                }
                _emit(
                    args,
                    {"status": "blocked", "review_status": status},
                    _review_status_text(status),
                )
                return 1
    elif args.command == "switch":
        st = flow_state.switch_profile(feature_dir, args.profile, actor, args.confirm, profiles_dir)
    elif args.command == "stage":
        if args.action == "start":
            st = flow_state.start_stage(feature_dir, args.stage, actor, profiles_dir)
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
        snapshot = audit.snapshot(feature_dir) if args.command == "context" else None
        broken = snapshot.problem if snapshot is not None else audit.verify_chain(feature_dir)
        if broken:
            raise FlowError(f"audit trail integrity problem: {broken}")
        if args.command == "context":
            assert snapshot is not None
            if not snapshot.event_count:
                raise FlowError("audit trail is missing or empty; inspect before resuming")
            profile = flow_state.profile_for(feature_dir, st.profile, profiles_dir)
            payload = {
                **_state_summary(st),
                "feature_dir": str(feature_dir.resolve()),
                "execution": profile.execution,
                "parked": snapshot.parked,
                "artifacts": {
                    name: (feature_dir / name).is_file()
                    for name in ("spec.md", "plan.md", "tasks.md")
                },
                "tasks": trace_mod.task_progress(feature_dir),
                "note": "Read-only context; checkboxes are not verification or dispatch approval.",
            }
            text = _state_text(st) + "\n" + json.dumps(payload, indent=2)
        else:
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
