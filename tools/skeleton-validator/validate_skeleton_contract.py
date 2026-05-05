#!/usr/bin/env python3
"""Validate normalized skeleton inventory JSON against MAX_BIPED_v1 contract."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


VALID_SEVERITIES = {"warn", "fail", "pending_manual"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON: {path} ({exc})") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate skeleton inventory JSON against a skeleton contract."
    )
    parser.add_argument("contract_path", help="Path to skeleton contract JSON")
    parser.add_argument("skeleton_path", help="Path to normalized skeleton inventory JSON")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for structured validation result JSON",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code for warn status",
    )
    return parser.parse_args()


def minimal_validate_contract(contract: Dict[str, Any]) -> List[str]:
    required = [
        "schema_version",
        "contract_id",
        "required_bones",
        "required_hierarchy_edges",
        "naming_rules",
        "validation_rules",
        "manifest_integration",
    ]
    errors: List[str] = []
    for field in required:
        if field not in contract:
            errors.append(f"missing contract field: {field}")
    if contract.get("contract_id") != "MAX_BIPED_v1":
        errors.append("contract_id must be MAX_BIPED_v1")
    if not isinstance(contract.get("required_bones"), list):
        errors.append("required_bones must be an array")
    if not isinstance(contract.get("required_hierarchy_edges"), list):
        errors.append("required_hierarchy_edges must be an array")
    return errors


def validate_contract_with_schema(contract: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(contract), key=lambda e: list(e.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for error in errors:
        location = ".".join(str(p) for p in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return False, messages


def severity_or_default(raw: Any, default: str = "fail") -> str:
    text = str(raw or "").strip()
    if text in VALID_SEVERITIES:
        return text
    return default


def add_finding(
    findings: List[Dict[str, Any]],
    severity: str,
    rule_id: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    entry: Dict[str, Any] = {
        "severity": severity,
        "rule_id": rule_id,
        "message": message,
    }
    if details:
        entry["details"] = details
    findings.append(entry)


def status_from_findings(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")) for item in findings}
    if "fail" in severities:
        return "fail"
    if "pending_manual" in severities:
        return "pending_manual"
    if "warn" in severities:
        return "warn"
    return "pass"


def finding_counts(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"fail": 0, "warn": 0, "pending_manual": 0}
    for finding in findings:
        severity = str(finding.get("severity", ""))
        if severity in counts:
            counts[severity] += 1
    counts["pass"] = 1 if sum(counts.values()) == 0 else 0
    return counts


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    contract_path = resolve_path(repo_root, args.contract_path)
    skeleton_path = resolve_path(repo_root, args.skeleton_path)
    schema_path = repo_root / "schemas" / "maxine_skeleton_contract.schema.json"

    if not contract_path.exists():
        print(f"FAIL: contract file not found: {contract_path}")
        return 2
    if not skeleton_path.exists():
        print(f"FAIL: skeleton file not found: {skeleton_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: skeleton contract schema not found: {schema_path}")
        return 2

    try:
        contract = load_json(contract_path)
        skeleton = load_json(skeleton_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    minimal_contract_errors = minimal_validate_contract(contract)
    if minimal_contract_errors:
        print("FAIL: skeleton contract minimal validation failed.")
        for error in minimal_contract_errors:
            print(f"  - {error}")
        return 1

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, schema_errors = validate_contract_with_schema(contract, schema)
        if not ok:
            print("FAIL: skeleton contract schema validation failed.")
            for error in schema_errors:
                print(f"  - {error}")
            return 1
    else:
        print("INFO: jsonschema not available; using minimal contract validation.")

    findings: List[Dict[str, Any]] = []
    bones_raw = skeleton.get("bones", [])
    if not isinstance(bones_raw, list):
        print("FAIL: skeleton.bones must be an array.")
        return 1

    bones_by_name: Dict[str, Dict[str, Any]] = {}
    parent_by_name: Dict[str, str] = {}
    for item in bones_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        bones_by_name[name] = item
        parent = item.get("parent")
        parent_by_name[name] = "" if parent is None else str(parent).strip()

    required_bones = [str(b).strip() for b in contract.get("required_bones", []) if str(b).strip()]
    for bone in required_bones:
        if bone not in bones_by_name:
            add_finding(
                findings,
                "fail",
                "required_bone_missing",
                f"Required bone '{bone}' is missing.",
                {"bone": bone},
            )

    edges = contract.get("required_hierarchy_edges", [])
    if isinstance(edges, list):
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            parent = str(edge.get("parent", "")).strip()
            child = str(edge.get("child", "")).strip()
            severity = severity_or_default(edge.get("severity"), "fail")
            rule_id = str(edge.get("rule_id", "required_hierarchy_edge")).strip() or "required_hierarchy_edge"
            if not parent or not child:
                continue
            if child not in bones_by_name:
                add_finding(
                    findings,
                    severity,
                    rule_id,
                    f"Hierarchy edge child '{child}' is missing.",
                    {"expected_parent": parent, "child": child},
                )
                continue
            actual_parent = parent_by_name.get(child, "")
            if actual_parent != parent:
                add_finding(
                    findings,
                    severity,
                    rule_id,
                    f"Hierarchy edge mismatch for child '{child}': expected parent '{parent}', got '{actual_parent}'.",
                    {"expected_parent": parent, "actual_parent": actual_parent, "child": child},
                )

    validation_rules = contract.get("validation_rules", {}) if isinstance(contract.get("validation_rules"), dict) else {}
    root_rule = validation_rules.get("root_bone", {}) if isinstance(validation_rules.get("root_bone"), dict) else {}
    root_name = str(root_rule.get("required_name", "root")).strip() or "root"
    root_missing_sev = severity_or_default(root_rule.get("severity_if_missing"), "fail")
    if root_name not in bones_by_name:
        add_finding(
            findings,
            root_missing_sev,
            "root_bone_required",
            f"Root bone '{root_name}' is missing.",
            {"required_name": root_name},
        )

    pelvis_rule = validation_rules.get("pelvis_relationship", {}) if isinstance(validation_rules.get("pelvis_relationship"), dict) else {}
    accepted_pelvis = [
        str(name).strip()
        for name in pelvis_rule.get("accepted_names", [])
        if str(name).strip()
    ]
    required_parent = str(pelvis_rule.get("required_parent", root_name)).strip() or root_name
    sev_missing = severity_or_default(pelvis_rule.get("severity_if_missing"), "fail")
    sev_parent = severity_or_default(pelvis_rule.get("severity_if_parent_mismatch"), "fail")
    sev_ambiguous = severity_or_default(pelvis_rule.get("severity_if_ambiguous"), "pending_manual")

    pelvis_candidates = [name for name in accepted_pelvis if name in bones_by_name]
    if len(pelvis_candidates) == 0:
        add_finding(
            findings,
            sev_missing,
            "pelvis_required",
            "No accepted pelvis/hip bone was found.",
            {"accepted_names": accepted_pelvis},
        )
    elif len(pelvis_candidates) > 1:
        add_finding(
            findings,
            sev_ambiguous,
            "pelvis_ambiguous",
            "Multiple accepted pelvis/hip candidates were found.",
            {"candidates": pelvis_candidates},
        )
    else:
        pelvis_name = pelvis_candidates[0]
        actual_parent = parent_by_name.get(pelvis_name, "")
        if actual_parent != required_parent:
            add_finding(
                findings,
                sev_parent,
                "pelvis_parent_mismatch",
                f"Pelvis/hip bone '{pelvis_name}' must be child of '{required_parent}', got '{actual_parent}'.",
                {
                    "pelvis_name": pelvis_name,
                    "expected_parent": required_parent,
                    "actual_parent": actual_parent,
                },
            )

    naming_rules = contract.get("naming_rules", {}) if isinstance(contract.get("naming_rules"), dict) else {}
    side_suffixes = naming_rules.get("side_suffixes", {}) if isinstance(naming_rules.get("side_suffixes"), dict) else {}
    left_suffix = str(side_suffixes.get("left", "_l")).strip() or "_l"
    right_suffix = str(side_suffixes.get("right", "_r")).strip() or "_r"

    required_bases = [
        str(base).strip()
        for base in naming_rules.get("required_sided_bases", [])
        if str(base).strip()
    ]
    for base in required_bases:
        left_name = f"{base}{left_suffix}"
        right_name = f"{base}{right_suffix}"
        if left_name not in bones_by_name or right_name not in bones_by_name:
            add_finding(
                findings,
                "fail",
                "required_side_pair_missing",
                f"Required sided base '{base}' is missing left/right pair.",
                {"expected_left": left_name, "expected_right": right_name},
            )

    optional_pairs = naming_rules.get("optional_mirror_pairs", [])
    if isinstance(optional_pairs, list):
        for pair in optional_pairs:
            if not isinstance(pair, dict):
                continue
            left = str(pair.get("left", "")).strip()
            right = str(pair.get("right", "")).strip()
            severity = severity_or_default(pair.get("severity_on_missing_mirror"), "warn")
            if not left or not right:
                continue
            left_exists = left in bones_by_name
            right_exists = right in bones_by_name
            if left_exists != right_exists:
                add_finding(
                    findings,
                    severity,
                    "optional_mirror_pair_missing",
                    f"Optional mirror pair is incomplete: left='{left}' right='{right}'.",
                    {"left_exists": left_exists, "right_exists": right_exists},
                )

    forbidden_patterns = [
        str(pattern).strip()
        for pattern in naming_rules.get("forbidden_name_patterns", [])
        if str(pattern).strip()
    ]
    forbidden_severity = severity_or_default(
        naming_rules.get("severity_on_forbidden_pattern"), "fail"
    )
    for bone_name in bones_by_name:
        for pattern in forbidden_patterns:
            try:
                if re.fullmatch(pattern, bone_name):
                    add_finding(
                        findings,
                        forbidden_severity,
                        "forbidden_name_pattern",
                        f"Bone '{bone_name}' matches forbidden pattern '{pattern}'.",
                        {"bone": bone_name, "pattern": pattern},
                    )
                    break
            except re.error:
                add_finding(
                    findings,
                    "pending_manual",
                    "invalid_forbidden_pattern",
                    f"Contract contains invalid regex pattern '{pattern}'.",
                    {"pattern": pattern},
                )

    metadata = skeleton.get("metadata", {}) if isinstance(skeleton.get("metadata"), dict) else {}
    coord_meta = metadata.get("coordinate_system", {}) if isinstance(metadata.get("coordinate_system"), dict) else {}
    units_meta = metadata.get("units", {}) if isinstance(metadata.get("units"), dict) else {}
    coord_expected = contract.get("coordinate_assumptions", {}) if isinstance(contract.get("coordinate_assumptions"), dict) else {}
    unit_expected = contract.get("unit_assumptions", {}) if isinstance(contract.get("unit_assumptions"), dict) else {}

    coord_rule = validation_rules.get("coordinate_metadata", {}) if isinstance(validation_rules.get("coordinate_metadata"), dict) else {}
    coord_severity = severity_or_default(
        coord_rule.get("severity_if_missing_or_mismatch"), "warn"
    )
    for key in ("up_axis", "forward_axis", "handedness"):
        expected = str(coord_expected.get(key, "")).strip()
        actual = str(coord_meta.get(key, "")).strip()
        if not expected:
            continue
        if actual != expected:
            add_finding(
                findings,
                coord_severity,
                "coordinate_metadata_mismatch",
                f"Coordinate metadata '{key}' mismatch: expected '{expected}', got '{actual}'.",
                {"field": key, "expected": expected, "actual": actual},
            )

    unit_rule = validation_rules.get("unit_metadata", {}) if isinstance(validation_rules.get("unit_metadata"), dict) else {}
    unit_severity = severity_or_default(unit_rule.get("severity_if_missing_or_mismatch"), "warn")
    expected_unit = str(unit_expected.get("linear_unit", "")).strip()
    actual_unit = str(units_meta.get("linear_unit", "")).strip()
    if expected_unit and actual_unit != expected_unit:
        add_finding(
            findings,
            unit_severity,
            "unit_metadata_mismatch",
            f"Unit metadata mismatch: expected '{expected_unit}', got '{actual_unit}'.",
            {"expected": expected_unit, "actual": actual_unit},
        )

    status = status_from_findings(findings)
    counts = finding_counts(findings)
    contract_id = str(contract.get("contract_id", "MAX_BIPED_v1")).strip() or "MAX_BIPED_v1"
    skeleton_id = str(skeleton.get("skeleton_id", skeleton_path.stem)).strip() or skeleton_path.stem

    manifest_integration = contract.get("manifest_integration", {}) if isinstance(contract.get("manifest_integration"), dict) else {}
    check_id = str(manifest_integration.get("contract_check_id", "max_biped_v1_skeleton_contract")).strip()
    manifest_target = str(manifest_integration.get("manifest_target_path", "qc.gates[]")).strip()
    future_manifest_target = str(manifest_integration.get("future_manifest_target_path", "qc.checks[]")).strip()
    qc_status_field = str(manifest_integration.get("qc_status_field", "result")).strip() or "result"
    details_field = str(manifest_integration.get("details_field", "details")).strip() or "details"

    qc_check: Dict[str, Any] = {
        "check_id": check_id,
        "check_name": f"{contract_id} skeleton contract",
        qc_status_field: status,
        "severity": status,
        "contract_id": contract_id,
        "skeleton_id": skeleton_id,
        "finding_counts": counts,
        details_field: {
            "findings": findings,
            "source_skeleton_path": str(skeleton_path),
            "source_contract_path": str(contract_path),
        },
    }

    result_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "validator_id": "maxine_skeleton_contract_validator",
        "validator_version": "1.0.0",
        "contract_id": contract_id,
        "skeleton_id": skeleton_id,
        "status": status,
        "allow_warn": bool(args.allow_warn),
        "finding_counts": counts,
        "findings": findings,
        "manifest_attachment": {
            "target_path": manifest_target,
            "future_target_path": future_manifest_target,
            "qc_check": qc_check,
        },
        "created_utc": utc_now(),
    }

    if args.output:
        output_path = resolve_path(repo_root, args.output)
        try:
            write_json(output_path, result_payload)
        except Exception as exc:
            print(f"FAIL: unable to write output file: {exc}")
            return 2

    print(json.dumps(result_payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
