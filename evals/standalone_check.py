"""Standalone eval checker — validates cases.json schema without live backend.

This runner NEVER imports backend code. It:
  1. Loads and schema-validates the current suite-object cases.json
  2. Keeps compatibility with the older top-level JSON array fixture
  3. Prints case summaries or a markdown report for manual trace verification

Usage:
    python evals/standalone_check.py                          # validate all
    python evals/standalone_check.py --case E19               # single case
    python evals/standalone_check.py --report                 # generate markdown

Exit codes: 0 = all valid, 1 = schema error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple, TypeAlias

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.json"
Case: TypeAlias = dict[str, Any]


class EvalSuite(NamedTuple):
    """Normalized view over both eval schema generations."""

    schema_version: str
    suite_name: str
    description: str
    cases: list[Case]
    legacy_array: bool = False

    def with_cases(self, cases: list[Case]) -> EvalSuite:
        return self._replace(cases=cases)


SuiteLike: TypeAlias = EvalSuite | list[Case] | dict[str, Any]


# ---------------------------------------------------------------------------
# Schema — minimal checks without pulling in backend or Pydantic
# ---------------------------------------------------------------------------

REQUIRED_SUITE_CASE_FIELDS = {
    "id",
    "kind",
    "title",
    "priority",
    "input",
    "expected_route",
    "expected_guardian",
    "expected_tool_trajectory",
    "forbidden_behavior",
    "pass_criteria",
}
REQUIRED_LEGACY_CASE_FIELDS = {"case_id", "priority", "input", "expected", "forbidden"}
VALID_PRIORITIES = {"P0", "P1"}
VALID_SPEAKERS = {"pharmacist", "parent", "clerk", "system", "unknown"}
VALID_KINDS = {
    "audio_half_duplex",
    "browser_trace_replay",
    "card_selection",
    "confirmation_replay",
    "confirmed_action",
    "conversation_flow",
    "faithful_translation",
    "privacy_trace",
    "translation_timeout",
    "turn",
}
VALID_ROUTE_TYPES = {
    "pharmacy_risk",
    "privacy_risk",
    "response_needed",
    "passive_translation",
    "block",
    "family_action",
    "fallback",
}
VALID_GUARDIAN = {
    "block",
    "require_parent_confirmation",
    "allow",
}
VALID_ACTIONS = {
    "ask_pharmacist_to_confirm",
    "ask_pharmacist_to_write_down",
    "block",
    "ask_question",
    "save_after_confirmation",
    "notify_after_confirmation",
    "no_agent_speech",
    "show_only",
}
VALID_TOOLS = {
    "check_drug_interaction",
    "memory_search",
    "memory_write",
    "notify_family",
}
SUITE_ROUTE_TYPES = VALID_ROUTE_TYPES | {"not_applicable"}
SUITE_GUARDIAN_DECISIONS = VALID_GUARDIAN | {
    "approved_card_required",
    "confirmed_action_only",
    "not_applicable",
}


def coerce_suite(payload: Any) -> EvalSuite:
    """Normalize current and legacy JSON shapes before validation/reporting."""

    if isinstance(payload, list):
        return EvalSuite(
            schema_version="legacy-array",
            suite_name="legacy-eval-array",
            description="Legacy eval case list.",
            cases=payload,
            legacy_array=True,
        )
    if isinstance(payload, dict):
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise ValueError("suite object must contain a cases array")
        return EvalSuite(
            schema_version=str(payload.get("schema_version") or "unknown"),
            suite_name=str(payload.get("suite_name") or "unnamed-suite"),
            description=str(payload.get("description") or ""),
            cases=cases,
            legacy_array=False,
        )
    raise ValueError("cases.json must be a suite object or JSON array")


def load_suite(path: Path = CASES_PATH) -> EvalSuite:
    """Read cases.json and return a schema-normalized suite."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc
    return coerce_suite(payload)


def _as_suite(suite_or_cases: SuiteLike) -> EvalSuite:
    if isinstance(suite_or_cases, EvalSuite):
        return suite_or_cases
    return coerce_suite(suite_or_cases)


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_string_list(
    errors: list[str],
    idx: str,
    case: Case,
    field: str,
    *,
    non_empty: bool = True,
    allowed: set[str] | None = None,
) -> None:
    value = case.get(field)
    if not isinstance(value, list) or (non_empty and not value):
        errors.append(f"{idx}: {field} must be a non-empty list")
        return
    for item in value:
        if not _is_non_empty_string(item):
            errors.append(f"{idx}: {field} entries must be non-empty strings")
            return
        if allowed is not None and item not in allowed:
            errors.append(f"{idx}: {field} contains unknown value '{item}'")
            return


def _validate_suite_case(errors: list[str], idx: str, case: Case) -> str | None:
    missing = REQUIRED_SUITE_CASE_FIELDS - set(case.keys())
    if missing:
        errors.append(f"{idx}: missing fields {sorted(missing)}")
        return None

    cid = case["id"]
    if not _is_non_empty_string(cid):
        errors.append(f"{idx}: id must be a non-empty string")
        return None
    if not re.match(r"^E\d{2}$", cid):
        errors.append(f"{idx}: id '{cid}' does not match E##")

    if case.get("kind") not in VALID_KINDS:
        errors.append(f"{idx}: kind '{case.get('kind')}' unknown")
    if not _is_non_empty_string(case.get("title")):
        errors.append(f"{idx}: title must be a non-empty string")
    if case.get("priority") not in VALID_PRIORITIES:
        errors.append(f"{idx}: invalid priority '{case.get('priority')}'")

    inp = case.get("input", {})
    if not isinstance(inp, dict):
        errors.append(f"{idx}: input must be an object")
    else:
        if inp.get("speaker") not in VALID_SPEAKERS:
            errors.append(f"{idx}: unknown speaker '{inp.get('speaker')}'")
        if not _is_non_empty_string(inp.get("language")):
            errors.append(f"{idx}: input.language must be a non-empty string")
        if not _is_non_empty_string(inp.get("text")):
            errors.append(f"{idx}: input.text must be a non-empty string")

    if case.get("expected_route") not in SUITE_ROUTE_TYPES:
        errors.append(f"{idx}: expected_route '{case.get('expected_route')}' unknown")
    if case.get("expected_guardian") not in SUITE_GUARDIAN_DECISIONS:
        errors.append(f"{idx}: expected_guardian '{case.get('expected_guardian')}' unknown")

    _validate_string_list(
        errors,
        idx,
        case,
        "expected_tool_trajectory",
        non_empty=False,
        allowed=VALID_TOOLS,
    )
    _validate_string_list(errors, idx, case, "forbidden_behavior")
    _validate_string_list(errors, idx, case, "pass_criteria")
    return str(cid)


def _validate_legacy_case(errors: list[str], idx: str, case: Case) -> str | None:
    missing = REQUIRED_LEGACY_CASE_FIELDS - set(case.keys())
    if missing:
        errors.append(f"{idx}: missing fields {sorted(missing)}")
        return None

    cid = case["case_id"]
    if not _is_non_empty_string(cid):
        errors.append(f"{idx}: case_id must be a non-empty string")
        return None
    if not re.match(r"^EVAL-\d{3}-[a-z0-9-]+$", cid):
        errors.append(f"{idx}: case_id '{cid}' does not match EVAL-NNN-<slug>")

    if case.get("priority") not in VALID_PRIORITIES:
        errors.append(f"{idx}: invalid priority '{case.get('priority')}'")

    inp = case.get("input", {})
    if not isinstance(inp, dict):
        errors.append(f"{idx}: input must be an object")
    else:
        if inp.get("speaker") not in VALID_SPEAKERS:
            errors.append(f"{idx}: unknown speaker '{inp.get('speaker')}'")
        transcript = inp.get("transcript_en")
        if not _is_non_empty_string(transcript):
            errors.append(f"{idx}: input.transcript_en must be non-empty string")

    exp = case.get("expected", {})
    if not isinstance(exp, dict):
        errors.append(f"{idx}: expected must be an object")
    else:
        if exp.get("route_type") not in VALID_ROUTE_TYPES:
            errors.append(f"{idx}: expected.route_type '{exp.get('route_type')}' unknown")
        if exp.get("expected_guardian_decision") not in VALID_GUARDIAN:
            decision = exp.get("expected_guardian_decision")
            errors.append(f"{idx}: guardian decision '{decision}' unknown")
        if exp.get("expected_action") not in VALID_ACTIONS:
            errors.append(f"{idx}: action '{exp.get('expected_action')}' unknown")
        if not isinstance(exp.get("expected_agents"), list):
            errors.append(f"{idx}: expected_agents must be a list")

    if not isinstance(case.get("forbidden"), list):
        errors.append(f"{idx}: forbidden must be a list")
    return str(cid)


def validate(suite_or_cases: SuiteLike) -> list[str]:
    """Validate either the current suite object or the legacy array shape."""

    try:
        suite = _as_suite(suite_or_cases)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    seen_ids: set[str] = set()

    if not suite.legacy_array:
        if not _is_non_empty_string(suite.schema_version):
            errors.append("suite: schema_version must be a non-empty string")
        if not _is_non_empty_string(suite.suite_name):
            errors.append("suite: suite_name must be a non-empty string")

    for i, case in enumerate(suite.cases):
        idx = f"case[{i}]"
        if not isinstance(case, dict):
            errors.append(f"{idx}: case must be an object")
            continue

        # The current suite and legacy fixtures encode the same intent using
        # different key names, so the validators stay separate and explicit.
        cid = (
            _validate_legacy_case(errors, idx, case)
            if suite.legacy_array
            else _validate_suite_case(errors, idx, case)
        )
        if cid is None:
            continue

        if cid in seen_ids:
            errors.append(f"{idx}: duplicate case id '{cid}'")
        seen_ids.add(cid)

    return errors


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _case_id(case: Case) -> str:
    return str(case.get("id") or case.get("case_id") or "<missing>")


def _case_text(case: Case) -> str:
    inp = case.get("input", {})
    if not isinstance(inp, dict):
        return ""
    return str(inp.get("text") or inp.get("transcript_en") or "")


def _case_route(case: Case) -> str:
    if "expected_route" in case:
        return str(case["expected_route"])
    exp = case.get("expected", {})
    return str(exp.get("route_type", "")) if isinstance(exp, dict) else ""


def _case_guardian(case: Case) -> str:
    if "expected_guardian" in case:
        return str(case["expected_guardian"])
    exp = case.get("expected", {})
    key = "expected_guardian_decision"
    return str(exp.get(key, "")) if isinstance(exp, dict) else ""


def _case_action_or_kind(case: Case) -> str:
    if "kind" in case:
        return str(case["kind"])
    exp = case.get("expected", {})
    return str(exp.get("expected_action", "")) if isinstance(exp, dict) else ""


def _table_cell(value: object, limit: int | None = None) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    if limit is not None and len(text) > limit:
        return f"{text[: limit - 3]}..."
    return text


def generate_report(suite_or_cases: SuiteLike) -> str:
    suite = _as_suite(suite_or_cases)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Kith&Kin Eval Report — {now}\n"]

    p0 = [c for c in suite.cases if c.get("priority") == "P0"]
    p1 = [c for c in suite.cases if c.get("priority") == "P1"]

    lines.append(f"- **Suite:** {suite.suite_name}  ")
    lines.append(f"- **Schema:** {suite.schema_version}  ")
    lines.append(f"- **Total cases:** {len(suite.cases)}  ")
    lines.append(f"- **P0 (blocking):** {len(p0)}  ")
    lines.append(f"- **P1 (important):** {len(p1)}  \n")

    lines.append("| Case ID | Priority | Scenario | Expected Route | Guardian | Kind/Action |")
    lines.append("|---------|----------|----------|----------------|----------|-------------|")
    for c in suite.cases:
        lines.append(
            f"| {_table_cell(_case_id(c))} "
            f"| {_table_cell(c.get('priority', ''))} "
            f"| {_table_cell(_case_text(c), 60)} "
            f"| {_table_cell(_case_route(c))} "
            f"| {_table_cell(_case_guardian(c))} "
            f"| {_table_cell(_case_action_or_kind(c))} |"
        )

    lines.append("\n---\n### Manual Trace Verification\n")
    lines.append(
        "Run each case against the live backend and confirm:\n\n"
        "1. Route type matches `expected_route` (or legacy `expected.route_type`)\n"
        "2. Tool calls include the expected trajectory when declared\n"
        "3. Guardian decision matches the expected guardian contract\n"
        "4. No forbidden outputs or behaviours observed\n\n"
        "Log traces to `evals/traces/` for writeup screenshots.\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Kith&Kin standalone eval checker")
    parser.add_argument("--case", help="Validate a single case by ID")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    args = parser.parse_args()

    if not CASES_PATH.exists():
        print(f"ERROR: cases.json not found at {CASES_PATH}", file=sys.stderr)
        return 1

    try:
        suite = load_suite(CASES_PATH)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.case:
        cases = [case for case in suite.cases if _case_id(case) == args.case]
        if not cases:
            print(f"ERROR: case '{args.case}' not found", file=sys.stderr)
            return 1
        suite = suite.with_cases(cases)

    errors = validate(suite)
    if errors:
        print("SCHEMA ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        return 1

    if args.report:
        print(generate_report(suite))
    else:
        print(f"✅ {len(suite.cases)} case(s) passed schema validation")
        for c in suite.cases:
            print(f"   {_case_id(c)}  [{c.get('priority')}]  {_case_text(c)[:50]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
