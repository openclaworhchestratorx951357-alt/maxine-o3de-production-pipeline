#!/usr/bin/env python3
"""Verify sandbox fixture path-safety policy and candidate paths."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


DRIVE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate sandbox fixture path safety.")
    parser.add_argument(
        "--policy",
        default="docs/audits/phase2_sandbox_path_safety_policy.json",
        help="Path to sandbox path-safety policy JSON",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path value to validate (repeatable)",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_exists(root: Path, rel_paths: List[str], label: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{label} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in sanitize_required_absent(rel_paths):
        if (root / rel).exists():
            failures.append(f"required absent file exists: {rel}")


def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def validate_candidate_path(
    root: Path,
    sandbox_root_rel: str,
    forbidden_patterns: List[str],
    candidate: str,
) -> Tuple[bool, str]:
    raw = candidate.strip()
    if not raw:
        return False, "empty path"

    if raw.startswith("\\\\") or raw.startswith("//"):
        return False, "UNC path rejected"

    if DRIVE_PATH_RE.match(raw):
        return False, "Windows drive path rejected"

    candidate_path = Path(raw)
    if candidate_path.is_absolute():
        return False, "absolute path rejected"

    normalized = normalize_slashes(raw)
    lowered = normalized.lower()

    if ".." in candidate_path.parts or "/../" in f"/{normalized}/":
        return False, "parent traversal rejected"

    for pattern in forbidden_patterns:
        pattern_normalized = normalize_slashes(pattern).lower()
        if pattern_normalized and pattern_normalized in lowered:
            return False, f"forbidden path pattern matched: {pattern}"

    sandbox_abs = (root / sandbox_root_rel).resolve()
    resolved_abs = (root / candidate_path).resolve()

    if sandbox_abs not in resolved_abs.parents and resolved_abs != sandbox_abs:
        return False, "path escapes sandbox root"

    return True, f"accepted under sandbox root: {sandbox_root_rel}"


def main() -> int:
    args = parse_args()
    root = repo_root()

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = (root / policy_path).resolve()

    if not policy_path.exists():
        print(f"FAIL: missing policy file: {policy_path}")
        return 2

    try:
        policy = load_json(policy_path)
    except Exception as exc:
        print(f"FAIL: unable to parse policy JSON: {exc}")
        return 2

    failures: List[str] = []
    accepted: List[str] = []
    rejected: List[str] = []

    sandbox_root = policy.get("sandbox_root", "")
    required_dirs = policy.get("required_fixture_directories", [])
    required_absent = policy.get("required_absent_files", [])
    forbidden_patterns = policy.get("forbidden_path_patterns", [])

    if not isinstance(sandbox_root, str) or not sandbox_root:
        failures.append("policy.sandbox_root must be a non-empty string")
    else:
        if not (root / sandbox_root).exists():
            failures.append(f"sandbox root missing: {sandbox_root}")

    if not isinstance(required_dirs, list):
        failures.append("policy.required_fixture_directories must be an array")
        required_dirs = []
    if not isinstance(required_absent, list):
        failures.append("policy.required_absent_files must be an array")
        required_absent = []
    if not isinstance(forbidden_patterns, list):
        failures.append("policy.forbidden_path_patterns must be an array")
        forbidden_patterns = []

    check_exists(root, required_dirs, "required fixture directory", failures)
    check_absent(root, required_absent, failures)

    if isinstance(args.path, list):
        for supplied in args.path:
            ok, reason = validate_candidate_path(root, sandbox_root, forbidden_patterns, supplied)
            if ok:
                accepted.append(f"{supplied} ({reason})")
            else:
                rejected.append(f"{supplied} ({reason})")

    if accepted:
        print("Accepted paths:")
        for item in accepted:
            print(f" - {item}")
    if rejected:
        print("Rejected paths:")
        for item in rejected:
            print(f" - {item}")

    if failures or rejected:
        print("FAIL: sandbox path-safety verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox path-safety verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
