#!/usr/bin/env python3
"""Extract controlled screenshot evidence into a manifest-attachable QC payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_EVIDENCE_SOURCE_TYPES = {"fixture", "imported_capture", "future_runtime_capture"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
ALLOWED_TARGET = "qc.gates[]"
ALLOWED_FUTURE_TARGET = "qc.checks[]"
CHECK_ID = "screenshot_evidence_v1"
CONTRACT_ID = "SCREENSHOT_EVIDENCE_EXTRACTOR_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build screenshot evidence payload from a controlled source-index JSON. "
            "This command is evidence-only and does not run DCC/O3DE/AP execution."
        )
    )
    parser.add_argument(
        "--source-index",
        required=True,
        help="Path to screenshot source-index JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return exit 0 when status is warn.",
    )
    return parser.parse_args()


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
    blocked = lower_parts & BLOCKED_PATH_TOKENS
    if blocked:
        blocked_tokens = ", ".join(sorted(blocked))
        raise ValueError(f"{label} resolves to blocked path token(s): {blocked_tokens}.")

    return candidate


def finding(fid: str, severity: str, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": fid,
        "severity": severity,
        "status": "open",
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if severities:
        return "warn"
    return "pass"


def load_index(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    allowed_screenshot_root = (repo_root / "examples" / "sandbox").resolve()

    findings: List[Dict[str, Any]] = []
    scanned: List[Dict[str, Any]] = []

    try:
        source_index_path = resolve_safe_path(repo_root, args.source_index, "source_index")
    except ValueError as exc:
        findings.append(finding("source_index_path_invalid", "error", str(exc)))
        payload = {
            "status": "fail",
            "check_id": CHECK_ID,
            "contract_id": CONTRACT_ID,
            "findings": findings,
            "manifest_attachment": {
                "target_path": ALLOWED_TARGET,
                "future_target_path": ALLOWED_FUTURE_TARGET,
                "qc_check": {
                    "check_id": CHECK_ID,
                    "result": "fail",
                    "severity": "error",
                    "details": {"source_index_path": str(args.source_index)},
                },
            },
        }
        print(json.dumps(payload, indent=2))
        return 1

    if not source_index_path.exists():
        findings.append(
            finding(
                "source_index_missing",
                "error",
                "Screenshot source index file was not found.",
                {"source_index_path": str(source_index_path)},
            )
        )
        payload = {
            "status": "fail",
            "check_id": CHECK_ID,
            "contract_id": CONTRACT_ID,
            "findings": findings,
            "manifest_attachment": {
                "target_path": ALLOWED_TARGET,
                "future_target_path": ALLOWED_FUTURE_TARGET,
                "qc_check": {
                    "check_id": CHECK_ID,
                    "result": "fail",
                    "severity": "error",
                    "details": {"source_index_path": str(source_index_path)},
                },
            },
        }
        print(json.dumps(payload, indent=2))
        return 1

    try:
        source_index = load_index(source_index_path)
    except Exception as exc:
        findings.append(finding("source_index_parse_error", "error", f"Unable to parse source index JSON: {exc}"))
        payload = {
            "status": "fail",
            "check_id": CHECK_ID,
            "contract_id": CONTRACT_ID,
            "findings": findings,
            "manifest_attachment": {
                "target_path": ALLOWED_TARGET,
                "future_target_path": ALLOWED_FUTURE_TARGET,
                "qc_check": {
                    "check_id": CHECK_ID,
                    "result": "fail",
                    "severity": "error",
                    "details": {"source_index_path": str(source_index_path)},
                },
            },
        }
        print(json.dumps(payload, indent=2))
        return 1

    if source_index.get("schema_version") != "1.0.0":
        findings.append(
            finding(
                "schema_version_invalid",
                "error",
                "schema_version must be 1.0.0.",
                {"found": source_index.get("schema_version")},
            )
        )

    evidence_source_type = str(source_index.get("evidence_source_type", "")).strip()
    if evidence_source_type not in ALLOWED_EVIDENCE_SOURCE_TYPES:
        findings.append(
            finding(
                "evidence_source_type_invalid",
                "error",
                "evidence_source_type is invalid.",
                {"found": evidence_source_type, "allowed": sorted(ALLOWED_EVIDENCE_SOURCE_TYPES)},
            )
        )

    minimum_required = source_index.get("minimum_required", 1)
    if not isinstance(minimum_required, int) or minimum_required < 1:
        findings.append(
            finding(
                "minimum_required_invalid",
                "error",
                "minimum_required must be an integer >= 1.",
                {"found": minimum_required},
            )
        )
        minimum_required = 1

    screenshots = source_index.get("screenshots")
    if not isinstance(screenshots, list):
        findings.append(finding("screenshots_not_array", "error", "screenshots must be an array."))
        screenshots = []

    existing_count = 0
    for idx, item in enumerate(screenshots):
        if not isinstance(item, dict):
            findings.append(
                finding(
                    "screenshot_item_not_object",
                    "error",
                    "screenshot entry must be an object.",
                    {"index": idx},
                )
            )
            continue

        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            findings.append(
                finding(
                    "screenshot_path_missing",
                    "error",
                    "screenshot path is required.",
                    {"index": idx},
                )
            )
            continue

        try:
            screenshot_path = resolve_safe_path(repo_root, raw_path, f"screenshot_path[{idx}]")
        except ValueError as exc:
            findings.append(finding("screenshot_path_invalid", "error", str(exc), {"index": idx, "path": raw_path}))
            continue

        if not _path_within(screenshot_path, allowed_screenshot_root):
            findings.append(
                finding(
                    "screenshot_root_violation",
                    "error",
                    "screenshot path must remain under examples/sandbox.",
                    {"index": idx, "path": str(screenshot_path)},
                )
            )
            continue

        ext = screenshot_path.suffix.lower()
        if evidence_source_type != "fixture" and ext not in ALLOWED_EXTENSIONS:
            findings.append(
                finding(
                    "screenshot_extension_unrecognized",
                    "warning",
                    "screenshot uses a non-standard extension.",
                    {"index": idx, "path": str(screenshot_path), "extension": ext},
                )
            )

        exists = screenshot_path.exists()
        if not exists:
            findings.append(
                finding(
                    "screenshot_missing",
                    "error",
                    "screenshot file does not exist.",
                    {"index": idx, "path": str(screenshot_path)},
                )
            )
        else:
            existing_count += 1

        scanned.append(
            {
                "index": idx,
                "path": str(screenshot_path),
                "exists": exists,
                "extension": ext,
                "label": item.get("label"),
            }
        )

    if existing_count < minimum_required:
        findings.append(
            finding(
                "minimum_required_not_met",
                "error",
                "minimum required screenshot count was not met.",
                {"minimum_required": minimum_required, "existing_count": existing_count},
            )
        )

    status = derive_status(findings)
    severity = "info" if status == "pass" else ("warning" if status == "warn" else "error")
    details = {
        "source_index_path": str(source_index_path),
        "evidence_source_type": evidence_source_type,
        "minimum_required": minimum_required,
        "discovered_count": len(scanned),
        "existing_count": existing_count,
        "screenshots": scanned,
        "allowed_root": str(allowed_screenshot_root),
        "execution_admitted": False,
    }
    payload = {
        "status": status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "findings": findings,
        "manifest_attachment": {
            "target_path": ALLOWED_TARGET,
            "future_target_path": ALLOWED_FUTURE_TARGET,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": status,
                "severity": severity,
                "details": details,
            },
        },
    }
    print(json.dumps(payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn":
        return 0 if args.allow_warn else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
