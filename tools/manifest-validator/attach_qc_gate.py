#!/usr/bin/env python3
"""Attach validator QC payloads to a MAXINE manifest in a deterministic, safe way."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_RESULTS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_SEVERITIES = {"info", "warning", "error", "manual_review"}
ALLOWED_TARGET_PATHS = {"qc.gates[]", "qc.checks[]"}
BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach one or more validator QC payloads into a MAXINE manifest."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to manifest JSON to update",
    )
    parser.add_argument(
        "--attachment",
        action="append",
        required=True,
        help="Path to validator output JSON payload (repeatable)",
    )
    parser.add_argument(
        "--allow-duplicate-check-id",
        action="store_true",
        help="Allow duplicate check_id entries in the destination QC list",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse JSON: {path} ({exc})") from exc


def _path_within(candidate: Path, parent: Path) -> bool:
    candidate_abs = candidate.resolve()
    parent_abs = parent.resolve()
    try:
        candidate_abs.relative_to(parent_abs)
        return True
    except ValueError:
        return False


def resolve_safe_path(repo_root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not _path_within(candidate, repo_root):
        raise ValueError(f"{label} must remain inside repository root.")

    lower_parts = {part.lower() for part in candidate.parts}
    if lower_parts & BLOCKED_PATH_TOKENS:
        blocked = sorted(lower_parts & BLOCKED_PATH_TOKENS)
        raise ValueError(
            f"{label} resolves to blocked path token(s): {', '.join(blocked)}."
        )

    return candidate


def validate_attachment_payload(data: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"attachment must be an object: {source_path}")

    attachment = data.get("manifest_attachment")
    if not isinstance(attachment, dict):
        raise ValueError(f"attachment missing manifest_attachment object: {source_path}")

    target_path = str(attachment.get("target_path", "")).strip()
    if target_path not in ALLOWED_TARGET_PATHS:
        raise ValueError(
            f"attachment target_path must be one of {sorted(ALLOWED_TARGET_PATHS)}: {source_path}"
        )

    future_target_path = str(attachment.get("future_target_path", "")).strip()
    if future_target_path != "qc.checks[]":
        raise ValueError(
            "attachment future_target_path must be qc.checks[]: "
            f"{source_path}"
        )

    qc_check = attachment.get("qc_check")
    if not isinstance(qc_check, dict):
        raise ValueError(f"attachment missing manifest_attachment.qc_check object: {source_path}")

    check_id = str(qc_check.get("check_id", "")).strip()
    if not check_id:
        raise ValueError(f"qc_check.check_id is required: {source_path}")

    result = str(qc_check.get("result", "")).strip()
    if result not in ALLOWED_RESULTS:
        raise ValueError(
            f"qc_check.result must be one of {sorted(ALLOWED_RESULTS)}: {source_path}"
        )

    severity = str(qc_check.get("severity", "")).strip()
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError(
            f"qc_check.severity must be one of {sorted(ALLOWED_SEVERITIES)}: {source_path}"
        )

    details = qc_check.get("details")
    if not isinstance(details, dict):
        raise ValueError(f"qc_check.details must be an object: {source_path}")

    return {
        "target_path": target_path,
        "future_target_path": future_target_path,
        "qc_check": qc_check,
    }


def ensure_qc_arrays(manifest: Dict[str, Any]) -> None:
    qc = manifest.setdefault("qc", {})
    if not isinstance(qc, dict):
        raise ValueError("manifest qc field must be an object.")

    gates = qc.get("gates")
    checks = qc.get("checks")

    if gates is None:
        qc["gates"] = []
    elif not isinstance(gates, list):
        raise ValueError("manifest qc.gates must be an array when present.")

    if checks is None:
        qc["checks"] = []
    elif not isinstance(checks, list):
        raise ValueError("manifest qc.checks must be an array when present.")


def get_target_list(manifest: Dict[str, Any], target_path: str) -> List[Dict[str, Any]]:
    qc = manifest["qc"]
    if target_path == "qc.gates[]":
        return qc["gates"]
    if target_path == "qc.checks[]":
        return qc["checks"]
    raise ValueError(f"unsupported target path: {target_path}")


def derive_qc_overall(manifest: Dict[str, Any]) -> str:
    qc = manifest.get("qc", {})
    gates = qc.get("gates", [])
    checks = qc.get("checks", [])
    states: List[str] = []

    for item in gates + checks:
        if isinstance(item, dict):
            state = str(item.get("result", "")).strip()
            if state in ALLOWED_RESULTS:
                states.append(state)

    if "fail" in states:
        return "fail"
    if "pending_manual" in states:
        return "warn"
    if "warn" in states:
        return "warn"
    return "pass"


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2) + os.linesep

    fd, temp_name = tempfile.mkstemp(prefix=".manifest-qc-attach-", suffix=".tmp", dir=str(directory))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(raw)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        manifest_path = resolve_safe_path(repo_root, args.manifest, "manifest_path")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    if manifest_path.suffix.lower() != ".json":
        print("FAIL: manifest_path must be a .json file.")
        return 2
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    if not isinstance(manifest, dict):
        print("FAIL: manifest JSON must be an object.")
        return 2

    try:
        ensure_qc_arrays(manifest)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    parsed_attachments: List[Dict[str, Any]] = []
    for raw_attachment in args.attachment:
        try:
            attachment_path = resolve_safe_path(repo_root, raw_attachment, "attachment_path")
        except ValueError as exc:
            print(f"FAIL: {exc}")
            return 2
        if not attachment_path.exists():
            print(f"FAIL: attachment file not found: {attachment_path}")
            return 2

        try:
            attachment_data = load_json(attachment_path)
            parsed = validate_attachment_payload(attachment_data, attachment_path)
            parsed_attachments.append(parsed)
        except ValueError as exc:
            print(f"FAIL: {exc}")
            return 1

    seen_new: set[str] = set()
    for item in parsed_attachments:
        target = item["target_path"]
        qc_check = item["qc_check"]
        check_id = str(qc_check.get("check_id", "")).strip()
        dest = get_target_list(manifest, target)

        existing_ids = {
            str(entry.get("check_id", "")).strip()
            for entry in dest
            if isinstance(entry, dict)
        }

        if not args.allow_duplicate_check_id:
            if check_id in existing_ids:
                print(f"FAIL: duplicate check_id already exists at {target}: {check_id}")
                return 1
            if check_id in seen_new:
                print(f"FAIL: duplicate check_id present in provided attachments: {check_id}")
                return 1

        dest.append(qc_check)
        seen_new.add(check_id)

    manifest["qc"]["overall"] = derive_qc_overall(manifest)
    manifest.setdefault("provenance", {})
    if isinstance(manifest["provenance"], dict):
        manifest["provenance"]["qc_attachment_updated_utc"] = utc_now()

    try:
        atomic_write_json(manifest_path, manifest)
    except Exception as exc:
        print(f"FAIL: could not write manifest atomically: {exc}")
        return 1

    print(
        json.dumps(
            {
                "status": "attached",
                "manifest_path": str(manifest_path),
                "attached_count": len(parsed_attachments),
                "qc_overall": manifest["qc"]["overall"],
                "attached_check_ids": sorted(seen_new),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
