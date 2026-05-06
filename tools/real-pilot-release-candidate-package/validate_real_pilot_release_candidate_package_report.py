#!/usr/bin/env python3
"""Validate evidence-only real pilot release-candidate package proof from a manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1_REPORT"
CHECK_ID = "real_pilot_release_candidate_package_v1"
CONTRACT_ID = "REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
RELEASE_LANE = "release_character"

ALLOWED_GATE_RESULTS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real", "manual"}
ALLOWED_ASSET_TIER = {"hero", "npc", "prop", "environment"}

REQUIRED_GATE_REFS: List[str] = [
    "source_product_evidence_resolver_v1",
    "dcc_conform_v1",
    "max_biped_v1_skeleton_contract",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "manual_hero_review_v1",
    "aaa_performance_budget_v1",
    "release_package_bundle_v1",
    "release_promotion_decision_v1",
    "release_publication_preflight_v1",
    "release_publication_gate_set_v1",
    "pilot_release_chain_v1",
]

CORE_EVIDENCE_CLASS_POLICY: Dict[str, set[str]] = {
    "source_product_evidence_resolver_v1": {"imported", "controlled_real"},
    "dcc_conform_v1": {"controlled_real"},
    "max_biped_v1_skeleton_contract": {"controlled_real"},
    "material_uv_qc_v1": {"controlled_real"},
    "animation_smoke_v1": {"controlled_real"},
    "screenshot_evidence_v1": {"controlled_real"},
    "manual_hero_review_v1": {"manual", "controlled_real"},
    "aaa_performance_budget_v1": {"controlled_real"},
}

FALLBACK_EVIDENCE_CLASS_BY_CHECK_ID: Dict[str, str] = {
    "max_biped_v1_skeleton_contract": "controlled_real",
    "dcc_conform_v1": "controlled_real",
    "source_product_evidence_resolver_v1": "imported",
    "material_uv_qc_v1": "controlled_real",
    "animation_smoke_v1": "controlled_real",
    "screenshot_evidence_v1": "controlled_real",
    "manual_hero_review_v1": "manual",
    "aaa_performance_budget_v1": "controlled_real",
    "release_package_bundle_v1": "manual",
    "release_promotion_decision_v1": "manual",
    "release_publication_preflight_v1": "manual",
    "release_publication_gate_set_v1": "manual",
    "pilot_release_chain_v1": "future",
}

SAFE_STATUS_FIELDS = [
    "package_publication_status",
    "o3de_execution_status",
    "editor_execution_status",
    "runtime_execution_status",
    "asset_processor_execution_status",
    "dcc_execution_status",
    "blender_execution_status",
    "spawn_publish_status",
    "production_write_status",
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate evidence-only real pilot release-candidate package proof "
            "from a manifest qc.gates[] chain."
        )
    )
    parser.add_argument("manifest_path", help="Path to manifest JSON")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for structured report JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code for warn status.",
    )
    return parser.parse_args()


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    status: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    item: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "status": status,
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def status_to_qc_severity(status: str) -> str:
    if status == "pass":
        return "info"
    if status == "warn":
        return "warning"
    if status == "pending":
        return "manual_review"
    return "error"


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities:
        return "pending"
    if "warning" in severities:
        return "warn"
    return "pass"


def validate_schema_with_jsonschema(report: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda err: list(err.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return False, messages


def _normalize_gate_map(manifest: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    qc = manifest.get("qc") if isinstance(manifest.get("qc"), dict) else {}
    gates = qc.get("gates", [])
    if not isinstance(gates, list):
        add_finding(
            findings,
            "manifest_qc_gates_invalid",
            "error",
            "open",
            "manifest qc.gates must be an array.",
        )
        return {}

    gate_map: Dict[str, Dict[str, Any]] = {}
    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            add_finding(
                findings,
                "manifest_qc_gate_entry_invalid",
                "error",
                "open",
                "Each manifest qc.gates entry must be an object.",
                {"index": idx},
            )
            continue
        check_id = str(gate.get("check_id", gate.get("check", ""))).strip()
        if not check_id:
            add_finding(
                findings,
                "manifest_qc_gate_check_id_missing",
                "error",
                "open",
                "Each manifest qc.gates entry must include check_id (or legacy check).",
                {"index": idx},
            )
            continue
        if check_id not in gate_map:
            gate_map[check_id] = gate
    return gate_map


def _normalize_asset_tier(identity: Dict[str, Any]) -> str:
    tier = str(
        identity.get("asset_tier", identity.get("tier", identity.get("package_tier", "hero")))
    ).strip().lower()
    if tier in ALLOWED_ASSET_TIER:
        return tier
    return "hero"


def _package_type_for_tier(tier: str) -> str:
    if tier == "npc":
        return "npc_character"
    if tier == "prop":
        return "prop"
    if tier == "environment":
        return "environment_asset"
    return "hero_character"


def _candidate_id_for_manifest(manifest: Dict[str, Any], identity: Dict[str, Any]) -> str:
    qc = manifest.get("qc") if isinstance(manifest.get("qc"), dict) else {}
    gates = qc.get("gates", []) if isinstance(qc.get("gates"), list) else []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        candidate_id = str(details.get("candidate_id", "")).strip()
        if candidate_id:
            return candidate_id
    fallback = (
        str(identity.get("candidate_id", "")).strip()
        or str(identity.get("character_id", "")).strip()
        or str(identity.get("package_id", "")).strip()
        or "real-pilot-candidate-001"
    )
    return fallback


def _normalize_evidence_class(check_id: str, gate: Dict[str, Any]) -> str:
    details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
    details_class = str(details.get("evidence_class", "")).strip()
    if details_class in ALLOWED_EVIDENCE_CLASS:
        return details_class
    fallback = FALLBACK_EVIDENCE_CLASS_BY_CHECK_ID.get(check_id, "fixture")
    if fallback in ALLOWED_EVIDENCE_CLASS:
        return fallback
    return "fixture"


def _is_truthy_admission(value: Any) -> bool:
    if value is True:
        return True
    text = str(value).strip().lower()
    return text in {"true", "admitted", "allowed", "executed", "published"}


def _scan_for_false_admissions(
    gate_map: Dict[str, Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> None:
    blocked_bool_keys = {
        "execution_admitted",
        "publication_admitted",
        "runtime_execution_admitted",
        "spawn_publish_admitted",
        "package_publication_admitted",
    }
    blocked_status_keys = {
        "execution_status",
        "publication_status",
        "runtime_execution_status",
        "spawn_publish_status",
    }
    blocked_status_values = {"admitted", "allowed", "executed", "published"}

    for check_id, gate in gate_map.items():
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        for key in blocked_bool_keys:
            if key in details and _is_truthy_admission(details.get(key)):
                add_finding(
                    findings,
                    "false_admission_detected",
                    "error",
                    "open",
                    "Execution/publication admission must remain blocked for evidence-only package proof.",
                    {"check_id": check_id, "field": key, "actual": details.get(key)},
                )

        for key in blocked_status_keys:
            raw = str(details.get(key, "")).strip().lower()
            if raw in blocked_status_values:
                add_finding(
                    findings,
                    "false_status_admission_detected",
                    "error",
                    "open",
                    "Execution/publication status indicates admitted behavior in evidence-only slice.",
                    {"check_id": check_id, "field": key, "actual": raw},
                )


def _status_from_gate_result(result: str) -> str:
    result_norm = result.strip()
    if result_norm == "pass":
        return "pass"
    if result_norm == "warn":
        return "warn"
    if result_norm == "pending_manual":
        return "pending"
    return "fail"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = resolve_path(repo_root, args.manifest_path)
    schema_path = repo_root / "schemas" / "maxine_real_pilot_release_candidate_package_report.schema.json"

    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: schema not found: {schema_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    findings: List[Dict[str, Any]] = []
    gate_map = _normalize_gate_map(manifest, findings)

    job = manifest.get("job", {}) if isinstance(manifest.get("job"), dict) else {}
    identity = manifest.get("identity", {}) if isinstance(manifest.get("identity"), dict) else {}
    lane = str(job.get("lane", "")).strip() or RELEASE_LANE
    if lane != RELEASE_LANE:
        add_finding(
            findings,
            "non_release_lane_manifest",
            "warning",
            "open",
            "Manifest lane is not release_character; package proof check is advisory.",
            {"lane": lane},
        )

    job_id = str(job.get("job_id", "")).strip() or "unknown-job"
    package_id = (
        str(identity.get("package_id", "")).strip()
        or str(identity.get("character_id", "")).strip()
        or "unknown-package"
    )
    package_version = (
        str(identity.get("package_version", "")).strip()
        or str(identity.get("release_tag", "")).strip()
        or "v1"
    )
    asset_tier = _normalize_asset_tier(identity)
    package_type = _package_type_for_tier(asset_tier)
    candidate_id = _candidate_id_for_manifest(manifest, identity)

    missing_required_gate_refs: List[str] = []
    required_gate_result_map: Dict[str, str] = {}
    required_gate_class_map: Dict[str, str] = {}

    for check_id in REQUIRED_GATE_REFS:
        gate = gate_map.get(check_id)
        if gate is None:
            missing_required_gate_refs.append(check_id)
            add_finding(
                findings,
                "missing_required_gate_ref",
                "error",
                "open",
                "Required gate reference missing for real pilot release-candidate proof.",
                {"check_id": check_id},
            )
            continue

        result = str(gate.get("result", "")).strip()
        required_gate_result_map[check_id] = result
        if result not in ALLOWED_GATE_RESULTS:
            add_finding(
                findings,
                "invalid_required_gate_result",
                "error",
                "open",
                "Required gate result must be pass|warn|fail|pending_manual.",
                {"check_id": check_id, "result": result},
            )
        elif result == "warn":
            add_finding(
                findings,
                "required_gate_warn_result",
                "warning",
                "open",
                "Required gate has warn status; package proof may be warn.",
                {"check_id": check_id},
            )
        elif result == "pending_manual":
            add_finding(
                findings,
                "required_gate_pending_manual_result",
                "manual_review",
                "open",
                "Required gate is pending manual review.",
                {"check_id": check_id},
            )
        elif result == "fail":
            add_finding(
                findings,
                "required_gate_fail_result",
                "error",
                "open",
                "Required gate has fail status.",
                {"check_id": check_id},
            )

        evidence_class = _normalize_evidence_class(check_id, gate)
        required_gate_class_map[check_id] = evidence_class

    for check_id, allowed_classes in CORE_EVIDENCE_CLASS_POLICY.items():
        if check_id not in required_gate_class_map:
            continue
        actual_class = required_gate_class_map[check_id]
        if actual_class not in allowed_classes:
            add_finding(
                findings,
                "core_gate_evidence_class_insufficient",
                "error",
                "open",
                "Core AAA gate evidence class does not meet policy for release-candidate proof.",
                {
                    "check_id": check_id,
                    "actual_evidence_class": actual_class,
                    "allowed_evidence_classes": sorted(allowed_classes),
                },
            )

    _scan_for_false_admissions(gate_map, findings)

    controlled_real_gate_refs = sorted(
        [check_id for check_id, cls in required_gate_class_map.items() if cls == "controlled_real"]
    )
    fixture_gate_refs = sorted(
        [check_id for check_id, cls in required_gate_class_map.items() if cls == "fixture"]
    )
    imported_gate_refs = sorted(
        [check_id for check_id, cls in required_gate_class_map.items() if cls == "imported"]
    )
    manual_gate_refs = sorted(
        [check_id for check_id, cls in required_gate_class_map.items() if cls == "manual"]
    )

    blocking_findings = sorted(
        [str(item.get("id", "")).strip() for item in findings if str(item.get("severity")) == "error"]
    )
    warning_findings = sorted(
        [
            str(item.get("id", "")).strip()
            for item in findings
            if str(item.get("severity")) in {"warning", "manual_review"}
        ]
    )

    release_candidate_status = derive_status(findings)
    package_completeness_status = "fail" if missing_required_gate_refs else "pass"
    evidence_integrity_status = "fail" if blocking_findings else ("warn" if warning_findings else "pass")

    rollback_readiness_status = _status_from_gate_result(
        required_gate_result_map.get("release_publication_gate_set_v1", "fail")
    )
    publication_readiness_status = _status_from_gate_result(
        required_gate_result_map.get("release_publication_preflight_v1", "fail")
    )
    performance_budget_status = _status_from_gate_result(
        required_gate_result_map.get("aaa_performance_budget_v1", "fail")
    )
    manual_review_status = _status_from_gate_result(
        required_gate_result_map.get("manual_hero_review_v1", "fail")
    )

    evidence_bundle_refs: List[str] = []
    for gate in gate_map.values():
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        for key in ("report_path", "source_evidence_ref", "evidence_bundle_ref"):
            value = str(details.get(key, "")).strip()
            if value:
                evidence_bundle_refs.append(value)
    evidence_bundle_refs = sorted(set(evidence_bundle_refs))

    decision_summary = (
        "Real pilot release-candidate package proof is evidence-only and binds required gate "
        "references while keeping execution/publication blocked."
    )

    payload: Dict[str, Any] = {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "report_type": EXPECTED_REPORT_TYPE,
        "job_id": job_id,
        "lane": lane,
        "status": release_candidate_status,
        "package_id": package_id,
        "package_version": package_version,
        "package_type": package_type,
        "candidate_id": candidate_id,
        "asset_tier": asset_tier,
        "manifest_ref": str(manifest_path),
        "release_chain_ref": "pilot_release_chain_v1",
        "evidence_bundle_refs": evidence_bundle_refs,
        "required_gate_refs": list(REQUIRED_GATE_REFS),
        "controlled_real_gate_refs": controlled_real_gate_refs,
        "fixture_gate_refs": fixture_gate_refs,
        "imported_gate_refs": imported_gate_refs,
        "manual_gate_refs": manual_gate_refs,
        "missing_required_gate_refs": sorted(missing_required_gate_refs),
        "blocking_findings": blocking_findings,
        "warning_findings": warning_findings,
        "release_candidate_status": release_candidate_status,
        "package_completeness_status": package_completeness_status,
        "evidence_integrity_status": evidence_integrity_status,
        "rollback_readiness_status": rollback_readiness_status,
        "publication_readiness_status": publication_readiness_status,
        "performance_budget_status": performance_budget_status,
        "manual_review_status": manual_review_status,
        "decision_summary": decision_summary,
        "claim_status": "evidence_only",
        "safety": {
            "package_publication_status": "blocked",
            "o3de_execution_status": "blocked",
            "editor_execution_status": "blocked",
            "runtime_execution_status": "blocked",
            "asset_processor_execution_status": "blocked",
            "dcc_execution_status": "blocked",
            "blender_execution_status": "blocked",
            "spawn_publish_status": "blocked",
            "production_write_status": "blocked",
        },
        "findings": findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": release_candidate_status,
                "severity": status_to_qc_severity(release_candidate_status),
                "details": {
                    "contract_id": CONTRACT_ID,
                    "package_id": package_id,
                    "package_version": package_version,
                    "package_type": package_type,
                    "candidate_id": candidate_id,
                    "asset_tier": asset_tier,
                    "required_gate_count": len(REQUIRED_GATE_REFS),
                    "missing_required_gate_count": len(missing_required_gate_refs),
                    "controlled_real_gate_count": len(controlled_real_gate_refs),
                    "imported_gate_count": len(imported_gate_refs),
                    "manual_gate_count": len(manual_gate_refs),
                    "fixture_gate_count": len(fixture_gate_refs),
                    "claim_status": "evidence_only",
                    "validated_at_utc": utc_now(),
                    "safety": {field: "blocked" for field in SAFE_STATUS_FIELDS},
                },
            },
        },
    }

    # Schema-check the produced payload so the contract always stays aligned.
    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_schema_with_jsonschema(payload, schema)
        if not ok:
            for err in errors:
                add_finding(
                    payload["findings"],
                    "schema_validation_error",
                    "error",
                    "open",
                    "Generated package proof payload failed schema validation.",
                    {"error": err},
                )
            payload["status"] = "fail"
            payload["release_candidate_status"] = "fail"
            payload["manifest_attachment"]["qc_check"]["result"] = "fail"
            payload["manifest_attachment"]["qc_check"]["severity"] = "error"
            payload["blocking_findings"] = sorted(
                [str(item.get("id", "")).strip() for item in payload["findings"] if str(item.get("severity")) == "error"]
            )

    if args.output:
        output_path = resolve_path(repo_root, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))

    final_status = str(payload.get("status", "fail"))
    if final_status == "pass":
        return 0
    if final_status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
