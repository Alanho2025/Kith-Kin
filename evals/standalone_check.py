"""Standalone eval checker — validates cases.json schema and traces WITHOUT live backend.

This runner NEVER imports backend code. It:
  1. Loads and schema-validates cases.json
  2. Prints case summaries for manual trace verification
  3. Generates a markdown report for the writeup

Usage:
    python evals/standalone_check.py                          # validate all
    python evals/standalone_check.py --case EVAL-015          # single case
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

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.json"

# ---------------------------------------------------------------------------
# Schema — minimal check without pulling in Pydantic
# ---------------------------------------------------------------------------

REQUIRED_CASE_FIELDS = {"case_id", "priority", "input", "expected", "forbidden"}
VALID_PRIORITIES = {"P0", "P1"}
VALID_SPEAKERS = {"pharmacist", "parent", "clerk", "unknown"}
VALID_ROUTE_TYPES = {
    "pharmacy_risk", "privacy_risk", "response_needed",
    "passive_translation", "block", "family_action", "fallback",
}
VALID_GUARDIAN = {
    "block", "require_parent_confirmation", "allow",
}
VALID_ACTIONS = {
    "ask_pharmacist_to_confirm", "ask_pharmacist_to_write_down",
    "block", "ask_question", "save_after_confirmation",
    "notify_after_confirmation", "no_agent_speech", "show_only",
}


def validate(cases: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, case in enumerate(cases):
        idx = f"case[{i}]"

        # Required top-level fields
        missing = REQUIRED_CASE_FIELDS - set(case.keys())
        if missing:
            errors.append(f"{idx}: missing fields {missing}")
            continue

        cid = case["case_id"]
        if cid in seen_ids:
            errors.append(f"{idx}: duplicate case_id '{cid}'")
        seen_ids.add(cid)

        if not re.match(r"^EVAL-\d{3}-[a-z0-9-]+$", cid):
            errors.append(f"{idx}: case_id '{cid}' does not match EVAL-NNN-<slug>")

        if case.get("priority") not in VALID_PRIORITIES:
            errors.append(f"{idx}: invalid priority '{case.get('priority')}'")

        inp = case.get("input", {})
        if inp.get("speaker") not in VALID_SPEAKERS:
            errors.append(f"{idx}: unknown speaker '{inp.get('speaker')}'")
        if not isinstance(inp.get("transcript_en"), str) or not inp["transcript_en"].strip():
            errors.append(f"{idx}: input.transcript_en must be non-empty string")

        exp = case.get("expected", {})
        if exp.get("route_type") not in VALID_ROUTE_TYPES:
            errors.append(f"{idx}: expected.route_type '{exp.get('route_type')}' unknown")
        if exp.get("expected_guardian_decision") not in VALID_GUARDIAN:
            errors.append(f"{idx}: guardian decision '{exp.get('expected_guardian_decision')}' unknown")
        if exp.get("expected_action") not in VALID_ACTIONS:
            errors.append(f"{idx}: action '{exp.get('expected_action')}' unknown")
        if not isinstance(exp.get("expected_agents"), list):
            errors.append(f"{idx}: expected_agents must be a list")

    return errors


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def generate_report(cases: list[dict]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Kith&Kin Eval Report — {now}\n"]

    p0 = [c for c in cases if c["priority"] == "P0"]
    p1 = [c for c in cases if c["priority"] == "P1"]

    lines.append(f"- **Total cases:** {len(cases)}  ")
    lines.append(f"- **P0 (blocking):** {len(p0)}  ")
    lines.append(f"- **P1 (important):** {len(p1)}  \n")

    lines.append("| Case ID | Priority | Scenario | Expected Route | Guardian | Action |")
    lines.append("|---------|----------|----------|----------------|----------|--------|")
    for c in cases:
        inp = c["input"]
        exp = c["expected"]
        scenario = inp["transcript_en"][:60]
        lines.append(
            f"| {c['case_id']} | {c['priority']} "
            f"| {scenario} "
            f"| {exp['route_type']} "
            f"| {exp['expected_guardian_decision']} "
            f"| {exp['expected_action']} |"
        )

    lines.append("\n---\n### Manual Trace Verification\n")
    lines.append(
        "Run each case against the live backend and confirm:\n\n"
        "1. Route type matches `expected.route_type`\n"
        "2. Tool calls include `expected_tool_calls`\n"
        "3. Guardian decision matches `expected_guardian_decision`\n"
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

    raw = CASES_PATH.read_text(encoding="utf-8")
    try:
        cases = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse error: {e}", file=sys.stderr)
        return 1

    if not isinstance(cases, list):
        print("ERROR: cases.json must be a JSON array", file=sys.stderr)
        return 1

    if args.case:
        cases = [c for c in cases if c["case_id"] == args.case]
        if not cases:
            print(f"ERROR: case '{args.case}' not found", file=sys.stderr)
            return 1

    errors = validate(cases)
    if errors:
        print("SCHEMA ERRORS:")
        for e in errors:
            print(f"  ❌ {e}")
        return 1

    if args.report:
        print(generate_report(cases))
    else:
        print(f"✅ {len(cases)} case(s) passed schema validation")
        for c in cases:
            print(f"   {c['case_id']}  [{c['priority']}]  {c['input']['transcript_en'][:50]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
