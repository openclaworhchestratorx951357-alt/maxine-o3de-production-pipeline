#!/usr/bin/env python3
"""Validate the static command-pack admission precheck report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_REL = Path("examples/execution-admission/command_pack_admission_precheck_report_v1.json")
SCHEMA_REL = Path("schemas/maxine_command_pack_admission_precheck_report.schema.json")

EXPECTED_SOURCE_PATHS = {
    "command_pack": "examples/execution-admission/natural_language_o3de_command_pack_v1.json",
    "command_pack_validator": "tools/execution-admission/validate_natural_language_o3de_command_pack.py",
    "pr_92_audit": "examples/execution-admission/pr_92_natural_language_command_pack_audit_v1.json",
    "pr_92_supersession": "examples/execution-admission/pr_92_supersession_record_v1.json",
    "candidate_matrix": "examples/execution-admission/execution_admission_candidate_matrix_v1.json",
    "runner_interface": "examples/execution-admission/release_candidate_package_publish_dry_run_runner_interface_v1.json",
    "sandbox_boundary": "examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json",
    "receipt_contract": "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json",
    "safety_verifier": "tools/audit/verify_sandbox_writer_safety.py",
    "proof_flow": "tools/release-lane/prove_pilot_release_chain.py",
    "production_readiness_report": "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json",
}

SOURCE_VALIDATORS = {
    "command_pack": (
        "tools/execution-admission/validate_natural_language_o3de_command_pack.py",
        "examples/execution-admission/natural_language_o3de_command_pack_v1.json",
    ),
    "pr_92_audit": (
        "tools/execution-admission/validate_pr_92_natural_language_command_pack_audit.py",
        "examples/execution-admission/pr_92_natural_language_command_pack_audit_v1.json",
    ),
    "pr_92_supersession": (
        "tools/execution-admission/validate_pr_92_supersession_record.py",
        "examples/execution-admission/pr_92_supersession_record_v1.json",
    ),
    "candidate_matrix": (
        "tools/execution-admission/validate_execution_admission_candidate_matrix.py",
        "examples/execution-admission/execution_admission_candidate_matrix_v1.json",
    ),
    "runner_interface": (
        "tools/execution-admission/validate_release_candidate_publication_dry_run_runner_interface.py",
        "examples/execution-admission/release_candidate_package_publish_dry_run_runner_interface_v1.json",
    ),
    "sandbox_boundary": (
        "tools/execution-admission/validate_release_candidate_publication_dry_run_sandbox_boundary.py",
        "examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json",
    ),
    "receipt_contract": (
        "tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py",
        "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json",
    ),
}

REQUIRED_FUTURE_ROUTING = {
    "command-pack validator",
    "candidate-specific admission",
    "runner interface contract",
    "sandbox boundary contract",
    "receipt contract",
    "safety verifier",
    "proof flow",
    "production-readiness gate",
}

REQUIRED_BEFORE_ADMISSION_REQUEST = {
    "explicit candidate ID selected",
    "command classification complete",
    "command maps to known candidate matrix entry or a new candidate matrix entry is proposed",
    "runner interface status validated",
    "sandbox boundary status validated",
    "receipt contract status validated",
    "admission blockers reviewed",
    "non-approval or approval decision state reviewed",
    "safety verifier passes",
    "proof flow passes",
    "production-readiness validator passes against generated manifest",
    "explicit operator approval only in future authorized slice if admission is requested",
}

REQUIRED_REFUSED_CATEGORIES = {
    "direct_o3de_execution",
    "editor_runtime_execution",
    "asset_processor_execution",
    "blender_dcc_execution",
    "screenshot_capture",
    "spawn_publish",
    "cache_live_db_access",
    "production_path_write",
    "engine_path_write",
    "authoritative_id_claim",
    "hidden_binary_execution",
    "approval_phrase_as_command",
    "bypass_admission_chain",
}

REQUIRED_BLOCKED_CATEGORIES = {
    "runner_required_runner_unimplemented",
    "gem_adapter_required_adapter_unimplemented",
    "dry_run_required_candidate_unadmitted",
    "receipt_required_receipt_unissued",
    "publication_required_publication_unadmitted",
    "production_ready_required_not_claimed",
}

ALLOWED_STATIC_CATEGORIES = {
    "static_evidence_only",
    "static_validation_report",
    "static_refusal_report",
    "static_command_envelope",
}

REQUIRED_PRECHECK_CLASSIFICATIONS = {
    "static_evidence_only",
    "read_only_status_candidate",
    "dry_run_candidate",
    "write_execute_candidate",
    "publish_spawn_candidate",
    "gem_adapter_candidate",
    "runner_candidate",
    "unsafe_command",
}

PROTECTED_FALSE_FIELDS = (
    "admission_request_eligible",
    "operator_approval_granted",
    "approval_phrase_present",
    "command_admitted",
    "runner_implemented",
    "runner_admitted",
    "runner_executed",
    "dry_run_admitted",
    "dry_run_executed",
    "receipt_issued",
    "real_execution_admitted",
    "publication_admitted",
    "production_ready_claimed",
    "direct_o3de_execution",
    "gem_adapter_implemented",
    "spawn_publish_allowed",
    "production_path_writes_allowed",
    "engine_path_writes_allowed",
    "cache_live_db_access_allowed",
)

EXPECTED_SOURCE_STATUS = {
    "command_pack_validator_status": "pass",
    "pr_92_audit_validator_status": "pass",
    "pr_92_supersession_validator_status": "pass",
    "candidate_matrix_validator_status": "pass",
    "runner_interface_validator_status": "pass",
    "sandbox_boundary_validator_status": "pass",
    "receipt_contract_validator_status": "pass",
    "safety_verifier_status": "pass",
    "proof_flow_status": "pass",
    "production_readiness_gate_status": "blocked_for_execution",
}

FORBIDDEN_LANGUAGE_PHRASES = (
    "precheck equals approval",
    "precheck equals approval-ready",
    "precheck equals command admission",
    "precheck equals dry-run admission",
    "precheck equals execution",
    "precheck equals runner implementation",
    "precheck equals gem adapter implementation",
    "precheck equals direct o3de control",
    "precheck equals publication",
    "precheck equals production_ready",
    "natural-language command pack can bypass runner interface",
    "natural-language command pack can bypass sandbox boundary",
    "natural-language command pack can bypass receipt contract",
    "natural-language command pack can bypass approval",
    "natural-language command pack can bypass admission",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a command-pack admission precheck report."
    )
    parser.add_argument(
        "report_path",
        nargs="?",
        default=str(DEFAULT_REPORT_REL),
        help="Path to the command-pack admission precheck report JSON.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path).strip())
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    finding: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        finding["details"] = details
    findings.append(finding)


def validate_schema(payload: Dict[str, Any], schema_path: Path) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return True, []

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    messages: List[str] = []
    for err in errors:
        location = ".".join(str(item) for item in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return not messages, messages


def _string_set(payload: Dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _iter_strings(value: Any) -> List[str]:
    results: List[str] = []
    if isinstance(value, dict):
        for child in value.values():
            results.extend(_iter_strings(child))
    elif isinstance(value, list):
        for child in value:
            results.extend(_iter_strings(child))
    elif isinstance(value, str):
        results.append(value)
    return results


def _validate_source_paths(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    source_artifacts = payload.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        add_finding(
            findings,
            "missing_source_artifacts",
            "error",
            "source_artifacts must be present.",
        )
        return

    for field, expected_path in EXPECTED_SOURCE_PATHS.items():
        artifact = source_artifacts.get(field)
        if not isinstance(artifact, dict):
            add_finding(
                findings,
                "missing_source_artifact",
                "error",
                "Required source artifact is missing.",
                {"field": field},
            )
            continue
        actual_path = str(artifact.get("path", "")).replace("\\", "/").strip()
        if actual_path != expected_path:
            add_finding(
                findings,
                "unexpected_source_artifact_path",
                "error",
                "Source artifact path must bind to the expected static artifact.",
                {"field": field, "expected": expected_path, "actual": actual_path},
            )
        if not actual_path or not resolve_path(actual_path).exists():
            add_finding(
                findings,
                "missing_source_artifact_path",
                "error",
                "Source artifact path does not exist.",
                {"field": field, "path": actual_path},
            )
        if artifact.get("validation_status") not in {"pass", "blocked_for_execution"}:
            add_finding(
                findings,
                "invalid_source_artifact_validation_status",
                "error",
                "Source artifact validation_status must be pass or blocked_for_execution.",
                {"field": field},
            )


def _validate_source_status(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    status = payload.get("source_artifact_validation_status")
    if not isinstance(status, dict):
        add_finding(
            findings,
            "missing_source_artifact_validation_status",
            "error",
            "source_artifact_validation_status must be present.",
        )
        return
    for field, expected in EXPECTED_SOURCE_STATUS.items():
        if status.get(field) != expected:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "Source artifact validation status has an unsafe value.",
                {"field": field, "expected": expected, "actual": status.get(field)},
            )


def _run_source_validators(findings: List[Dict[str, Any]]) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for name, (validator_rel, example_rel) in SOURCE_VALIDATORS.items():
        proc = subprocess.run(
            [
                sys.executable,
                str((REPO_ROOT / validator_rel).resolve()),
                str((REPO_ROOT / example_rel).resolve()),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        try:
            payload = json.loads(proc.stdout[proc.stdout.find("{") :])
        except Exception:
            payload = {}
        status = str(payload.get("status", "")).strip()
        if proc.returncode != 0 or status not in {"pass", "blocked"}:
            add_finding(
                findings,
                "source_validator_failed",
                "error",
                "Required source validator did not pass.",
                {
                    "source": name,
                    "returncode": proc.returncode,
                    "status": status,
                    "stderr": proc.stderr.strip(),
                },
            )
        results[f"{name}_status"] = status or "unknown"
    return results


def _precheck_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    prechecks = payload.get("command_envelope_prechecks")
    if not isinstance(prechecks, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for precheck in prechecks:
        if isinstance(precheck, dict):
            classification = str(precheck.get("classification", "")).strip()
            if classification:
                result[classification] = precheck
    return result


def _validate_top_level(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    if payload.get("precheck_status") != "static_precheck_valid_blocked":
        add_finding(
            findings,
            "invalid_precheck_status",
            "error",
            "precheck_status must remain static_precheck_valid_blocked.",
        )
    if payload.get("generated_from_static_artifacts_only") is not True:
        add_finding(
            findings,
            "not_generated_from_static_artifacts_only",
            "error",
            "generated_from_static_artifacts_only must be true.",
        )
    for field in PROTECTED_FALSE_FIELDS:
        if payload.get(field) is not False:
            add_finding(
                findings,
                "protected_status_field_true",
                "error",
                f"{field} must remain false.",
                {"field": field},
            )
    if payload.get("unsafe_claims_detected") is not False:
        add_finding(
            findings,
            "unsafe_claims_detected",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    global_result = payload.get("global_precheck_result")
    if not isinstance(global_result, dict):
        add_finding(
            findings,
            "missing_global_precheck_result",
            "error",
            "global_precheck_result must be present.",
        )
        return
    for field in (
        "structurally_valid",
        "static_command_envelopes_allowed_only_as_non_executing_artifacts",
        "execution_admission_runner_gem_publish_spawn_blocked_or_refused",
        "no_command_eligible_for_admission_request",
        "no_command_admitted",
        "no_runner_implemented",
        "no_gem_adapter_implemented",
        "no_direct_o3de_control",
        "production_readiness_unclaimed",
    ):
        if global_result.get(field) is not True:
            add_finding(
                findings,
                "global_precheck_result_not_blocked_static",
                "error",
                "global_precheck_result must preserve static blocked posture.",
                {"field": field},
            )


def _validate_lists(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    routing = _string_set(payload, "required_future_routing")
    for required in sorted(REQUIRED_FUTURE_ROUTING):
        if required not in routing:
            add_finding(
                findings,
                "missing_required_future_routing",
                "error",
                "required_future_routing is missing a required gate.",
                {"missing": required},
            )

    before = _string_set(payload, "required_before_admission_request")
    for required in sorted(REQUIRED_BEFORE_ADMISSION_REQUEST):
        if required not in before:
            add_finding(
                findings,
                "missing_required_before_admission_request",
                "error",
                "required_before_admission_request is missing a required item.",
                {"missing": required},
            )

    refused = _string_set(payload, "refused_command_categories")
    for required in sorted(REQUIRED_REFUSED_CATEGORIES):
        if required not in refused:
            add_finding(
                findings,
                "missing_refused_command_category",
                "error",
                "refused_command_categories is missing a required category.",
                {"missing": required},
            )

    blocked = _string_set(payload, "blocked_command_categories")
    for required in sorted(REQUIRED_BLOCKED_CATEGORIES):
        if required not in blocked:
            add_finding(
                findings,
                "missing_blocked_command_category",
                "error",
                "blocked_command_categories is missing a required category.",
                {"missing": required},
            )

    eligible = _string_set(payload, "eligible_static_categories")
    disallowed_static = sorted(eligible - ALLOWED_STATIC_CATEGORIES)
    if disallowed_static:
        add_finding(
            findings,
            "disallowed_eligible_static_category",
            "error",
            "eligible_static_categories may only contain static non-executing categories.",
            {"disallowed": disallowed_static},
        )


def _validate_prechecks(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    prechecks = _precheck_map(payload)
    for required in sorted(REQUIRED_PRECHECK_CLASSIFICATIONS):
        if required not in prechecks:
            add_finding(
                findings,
                "missing_command_envelope_precheck",
                "error",
                "command_envelope_prechecks is missing a required classification.",
                {"missing": required},
            )
    if findings:
        return

    static_precheck = prechecks["static_evidence_only"]
    if static_precheck.get("execution_required") is not False:
        add_finding(
            findings,
            "static_evidence_precheck_claims_execution",
            "error",
            "Static evidence-only precheck must remain non-executing.",
        )
    if static_precheck.get("admission_required") is not False:
        add_finding(
            findings,
            "static_evidence_precheck_claims_admission",
            "error",
            "Static evidence-only precheck must not require admission in this slice.",
        )
    if static_precheck.get("result") != "allowed_as_static_non_executing_artifact":
        add_finding(
            findings,
            "static_evidence_precheck_wrong_result",
            "error",
            "Static evidence-only precheck must be allowed only as a non-executing artifact.",
        )

    read_only_precheck = prechecks["read_only_status_candidate"]
    if read_only_precheck.get("live_o3de_readback_performed") is not False:
        add_finding(
            findings,
            "read_only_status_precheck_claims_live_readback",
            "error",
            "Read-only/status precheck must not perform live O3DE readback.",
        )
    if read_only_precheck.get("result") != "blocked_pending_read_only_policy_or_candidate_admission":
        add_finding(
            findings,
            "read_only_status_precheck_wrong_result",
            "error",
            "Read-only/status precheck must remain blocked pending policy or candidate admission.",
        )

    dry_run_precheck = prechecks["dry_run_candidate"]
    if dry_run_precheck.get("admitted") is not False:
        add_finding(
            findings,
            "dry_run_precheck_claims_admitted",
            "error",
            "Dry-run precheck must not claim admission.",
        )
    if dry_run_precheck.get("result") != "blocked_pending_candidate_specific_admission":
        add_finding(
            findings,
            "dry_run_precheck_wrong_result",
            "error",
            "Dry-run precheck must remain blocked pending candidate-specific admission.",
        )
    dry_run_gates = {
        str(item).strip()
        for item in dry_run_precheck.get("required_gates", [])
        if str(item).strip()
    }
    for gate in (
        "runner interface contract",
        "sandbox boundary contract",
        "receipt contract",
        "safety verifier",
        "proof flow",
    ):
        if gate not in dry_run_gates:
            add_finding(
                findings,
                "dry_run_precheck_missing_required_gate",
                "error",
                "Dry-run precheck is missing a required gate.",
                {"missing": gate},
            )

    write_precheck = prechecks["write_execute_candidate"]
    if write_precheck.get("result") not in {"refused_or_blocked", "refused", "blocked"}:
        add_finding(
            findings,
            "write_execute_precheck_not_refused_or_blocked",
            "error",
            "Write/execute precheck must be refused or blocked.",
        )

    publish_precheck = prechecks["publish_spawn_candidate"]
    if publish_precheck.get("result") != "refused":
        add_finding(
            findings,
            "publish_spawn_precheck_not_refused",
            "error",
            "Publish/spawn precheck must be refused.",
        )

    gem_precheck = prechecks["gem_adapter_candidate"]
    if gem_precheck.get("gem_adapter_implemented") is not False:
        add_finding(
            findings,
            "gem_adapter_precheck_claims_adapter_implemented",
            "error",
            "Gem adapter precheck must keep adapter unimplemented.",
        )
    if gem_precheck.get("result") != "blocked":
        add_finding(
            findings,
            "gem_adapter_precheck_not_blocked",
            "error",
            "Gem adapter precheck must remain blocked.",
        )

    runner_precheck = prechecks["runner_candidate"]
    if (
        runner_precheck.get("runner_implemented") is not False
        or runner_precheck.get("runner_admitted") is not False
    ):
        add_finding(
            findings,
            "runner_precheck_claims_runner_available",
            "error",
            "Runner precheck must keep runner unimplemented and unadmitted.",
        )
    if runner_precheck.get("result") != "blocked":
        add_finding(
            findings,
            "runner_precheck_not_blocked",
            "error",
            "Runner precheck must remain blocked.",
        )

    unsafe_precheck = prechecks["unsafe_command"]
    if unsafe_precheck.get("result") != "refused":
        add_finding(
            findings,
            "unsafe_precheck_not_refused",
            "error",
            "Unsafe command precheck must be refused.",
        )

    for classification, precheck in prechecks.items():
        if precheck.get("admission_request_eligible") is not False:
            add_finding(
                findings,
                "precheck_claims_admission_request_eligible",
                "error",
                "No command envelope precheck may be admission-request eligible in this slice.",
                {"classification": classification},
            )
        if precheck.get("runner_implemented") is not False:
            add_finding(
                findings,
                "precheck_claims_runner_implemented",
                "error",
                "No command envelope precheck may claim a runner implementation.",
                {"classification": classification},
            )
        if precheck.get("gem_adapter_implemented") is not False:
            add_finding(
                findings,
                "precheck_claims_gem_adapter_implemented",
                "error",
                "No command envelope precheck may claim a Gem adapter implementation.",
                {"classification": classification},
            )


def _validate_language(payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    text = "\n".join(_iter_strings(payload)).lower()
    for phrase in FORBIDDEN_LANGUAGE_PHRASES:
        if phrase in text:
            add_finding(
                findings,
                "unsafe_precheck_language",
                "error",
                "Report contains forbidden unsafe precheck language.",
                {"phrase": phrase},
            )


def validate_payload(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], Dict[str, str]]:
    findings: List[Dict[str, Any]] = []
    _validate_source_paths(payload, findings)
    _validate_source_status(payload, findings)
    _validate_top_level(payload, findings)
    _validate_lists(payload, findings)
    _validate_prechecks(payload, findings)
    _validate_language(payload, findings)

    source_validator_results: Dict[str, str] = {}
    if not any(finding["severity"] == "error" for finding in findings):
        source_validator_results = _run_source_validators(findings)

    status = "fail" if any(item["severity"] == "error" for item in findings) else "pass"
    return status, findings, source_validator_results


def main() -> int:
    args = parse_args()
    report_path = resolve_path(args.report_path)

    findings: List[Dict[str, Any]] = []
    try:
        payload = load_json(report_path)
    except Exception as exc:
        report = {
            "schema_version": "1.0.0",
            "report_type": "COMMAND_PACK_ADMISSION_PRECHECK_VALIDATION_v1_REPORT",
            "status": "fail",
            "report_path": str(report_path),
            "command_pack_admission_precheck_present": False,
            "command_pack_admission_precheck_valid": False,
            "findings": [
                {
                    "id": "report_load_failed",
                    "severity": "error",
                    "message": f"Unable to load report JSON: {exc}",
                }
            ],
        }
        print(json.dumps(report, indent=2))
        return 1

    schema_ok, schema_messages = validate_schema(payload, REPO_ROOT / SCHEMA_REL)
    if not schema_ok:
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    payload_status, payload_findings, source_validator_results = validate_payload(payload)
    findings.extend(payload_findings)
    status = "fail" if findings or payload_status == "fail" else "pass"

    refused_count = len(payload.get("refused_command_categories", []))
    blocked_count = len(payload.get("blocked_command_categories", []))
    static_count = len(payload.get("eligible_static_categories", []))
    summary = (
        "Command-pack admission precheck is static and blocked; "
        "no command is admitted or eligible to request admission in this slice."
    )

    report = {
        "schema_version": "1.0.0",
        "report_type": "COMMAND_PACK_ADMISSION_PRECHECK_VALIDATION_v1_REPORT",
        "status": status,
        "summary": summary,
        "report_path": str(report_path),
        "command_pack_admission_precheck_present": True,
        "command_pack_admission_precheck_valid": status == "pass",
        "precheck_status": payload.get("precheck_status"),
        "admission_request_eligible": payload.get("admission_request_eligible"),
        "command_admitted": payload.get("command_admitted"),
        "runner_implemented": payload.get("runner_implemented"),
        "runner_admitted": payload.get("runner_admitted"),
        "runner_executed": payload.get("runner_executed"),
        "dry_run_admitted": payload.get("dry_run_admitted"),
        "dry_run_executed": payload.get("dry_run_executed"),
        "receipt_issued": payload.get("receipt_issued"),
        "real_execution_admitted": payload.get("real_execution_admitted"),
        "publication_admitted": payload.get("publication_admitted"),
        "production_ready_claimed": payload.get("production_ready_claimed"),
        "refused_command_categories_count": refused_count,
        "blocked_command_categories_count": blocked_count,
        "eligible_static_categories_count": static_count,
        "source_validator_results": source_validator_results,
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
