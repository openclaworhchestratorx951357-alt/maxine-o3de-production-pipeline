#!/usr/bin/env python3
"""Verify a planning-only sandbox execution intent artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_INTENT_STATUS = {"intent_recorded", "intent_blocked", "intent_hold"}
REQUIRED_INTENT_FIELDS = [
    "schema_version",
    "intent_id",
    "final_preflight_report_id",
    "sandbox_write_plan_id",
    "sandbox_id",
    "intent_status",
    "intent_scope",
    "intent_recorded_by",
    "intent_recorded_at_utc",
    "notes",
    "safety",
]
REQUIRED_SAFETY = {
    "execution_intent_only": True,
    "implementation_available": False,
    "sandbox_write_allowed": False,
    "rollback_execution_allowed": False,
    "authoritative_write_allowed": False,
    "production_paths_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox execution intent JSON.")
    parser.add_argument("--intent", required=True, help="Path to sandbox execution intent JSON")
    parser.add_argument("--final-preflight-report", required=True, help="Path to sandbox final preflight report JSON")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_input_path(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def main() -> int:
    args = parse_args()
    root = repo_root()

    intent_path = resolve_input_path(root, args.intent)
    report_path = resolve_input_path(root, args.final_preflight_report)

    if not intent_path.exists():
        print(f"FAIL: missing execution intent JSON: {intent_path}")
        return 2

    if not report_path.exists():
        print(f"FAIL: missing final preflight report JSON: {report_path}")
        return 2

    try:
        intent = load_json(intent_path)
    except Exception as exc:
        print(f"FAIL: unable to parse execution intent JSON: {exc}")
        return 2

    try:
        report = load_json(report_path)
    except Exception as exc:
        print(f"FAIL: unable to parse final preflight report JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_INTENT_FIELDS:
        if field not in intent:
            failures.append(f"missing required intent field: {field}")

    if intent.get("intent_status") not in ALLOWED_INTENT_STATUS:
        failures.append("intent_status must be one of: intent_recorded, intent_blocked, intent_hold")

    if intent.get("intent_scope") != "sandbox_only_implementation_planning":
        failures.append("intent_scope must equal sandbox_only_implementation_planning")

    if intent.get("final_preflight_report_id") != report.get("preflight_report_id"):
        failures.append("final_preflight_report_id must match final preflight report preflight_report_id")

    if intent.get("sandbox_write_plan_id") != report.get("sandbox_write_plan_id"):
        failures.append("sandbox_write_plan_id must match final preflight report sandbox_write_plan_id")

    if intent.get("sandbox_id") != report.get("sandbox_id"):
        failures.append("sandbox_id must match final preflight report sandbox_id")

    safety = intent.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    if failures:
        print("FAIL: sandbox execution intent verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox execution intent verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
