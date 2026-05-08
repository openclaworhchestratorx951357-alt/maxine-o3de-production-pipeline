import copy
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_command_pack_admission_precheck_report.py"
)
EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "command_pack_admission_precheck_report_v1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run(path: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=1200,
    )
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def _finding_ids(report: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in report.get("findings", [])
        if isinstance(item, dict)
    }


def _invalid_variant(tmp_path: Path, payload: dict, name: str) -> tuple[int, set[str]]:
    path = tmp_path / f"{name}.json"
    _write(path, payload)
    code, report = _run(path)
    return code, _finding_ids(report)


def _precheck(payload: dict, classification: str) -> dict:
    for item in payload["command_envelope_prechecks"]:
        if item["classification"] == classification:
            return item
    raise AssertionError(f"missing precheck classification: {classification}")


def test_valid_command_pack_admission_precheck_report_validates():
    code, report = _run(EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["precheck_status"] == "static_precheck_valid_blocked"
    assert report["admission_request_eligible"] is False
    assert report["command_admitted"] is False
    assert report["runner_implemented"] is False
    assert report["production_ready_claimed"] is False


SOURCE_ARTIFACT_FIELDS = [
    "command_pack",
    "pr_92_audit",
    "pr_92_supersession",
    "runner_interface",
    "sandbox_boundary",
    "receipt_contract",
    "candidate_matrix",
]


def test_rejects_missing_required_source_artifact(tmp_path: Path):
    for field in SOURCE_ARTIFACT_FIELDS:
        payload = _load(EXAMPLE)
        payload["source_artifacts"][field]["path"] = "examples/execution-admission/missing.json"
        code, ids = _invalid_variant(tmp_path, payload, f"missing-{field}")
        assert code != 0
        assert "missing_source_artifact_path" in ids


def test_rejects_precheck_status_that_implies_approval_or_admission(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["precheck_status"] = "approval_ready"
    code, ids = _invalid_variant(tmp_path, payload, "approval-ready-status")
    assert code != 0
    assert "invalid_precheck_status" in ids or "schema_validation_error" in ids


PROTECTED_FALSE_FIELDS = [
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
]


def test_rejects_any_protected_status_claim_true(tmp_path: Path):
    for field in PROTECTED_FALSE_FIELDS:
        payload = _load(EXAMPLE)
        payload[field] = True
        code, ids = _invalid_variant(tmp_path, payload, f"{field}-true")
        assert code != 0
        assert "protected_status_field_true" in ids or "schema_validation_error" in ids


REQUIRED_CLASSIFICATIONS = [
    "static_evidence_only",
    "read_only_status_candidate",
    "dry_run_candidate",
    "write_execute_candidate",
    "publish_spawn_candidate",
    "gem_adapter_candidate",
    "runner_candidate",
    "unsafe_command",
]


def test_report_contains_all_representative_command_envelope_prechecks():
    payload = _load(EXAMPLE)
    classifications = {
        item["classification"] for item in payload["command_envelope_prechecks"]
    }
    for classification in REQUIRED_CLASSIFICATIONS:
        assert classification in classifications


def test_rejects_missing_representative_command_envelope_precheck(tmp_path: Path):
    for classification in REQUIRED_CLASSIFICATIONS:
        payload = _load(EXAMPLE)
        payload["command_envelope_prechecks"] = [
            item
            for item in payload["command_envelope_prechecks"]
            if item["classification"] != classification
        ]
        code, ids = _invalid_variant(tmp_path, payload, f"missing-{classification}")
        assert code != 0
        assert "missing_command_envelope_precheck" in ids


def test_rejects_static_evidence_precheck_if_it_claims_execution(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "static_evidence_only")
    precheck["execution_required"] = True
    code, ids = _invalid_variant(tmp_path, payload, "static-evidence-executes")
    assert code != 0
    assert "static_evidence_precheck_claims_execution" in ids


def test_rejects_read_only_status_precheck_if_it_claims_live_readback(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "read_only_status_candidate")
    precheck["live_o3de_readback_performed"] = True
    code, ids = _invalid_variant(tmp_path, payload, "read-only-live-readback")
    assert code != 0
    assert "read_only_status_precheck_claims_live_readback" in ids


def test_rejects_dry_run_precheck_if_it_claims_admitted(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "dry_run_candidate")
    precheck["admitted"] = True
    code, ids = _invalid_variant(tmp_path, payload, "dry-run-admitted")
    assert code != 0
    assert "dry_run_precheck_claims_admitted" in ids


def test_rejects_write_execute_precheck_if_not_refused_or_blocked(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "write_execute_candidate")
    precheck["result"] = "allowed"
    code, ids = _invalid_variant(tmp_path, payload, "write-execute-allowed")
    assert code != 0
    assert "write_execute_precheck_not_refused_or_blocked" in ids


def test_rejects_publish_spawn_precheck_if_not_refused(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "publish_spawn_candidate")
    precheck["result"] = "blocked"
    code, ids = _invalid_variant(tmp_path, payload, "publish-spawn-not-refused")
    assert code != 0
    assert "publish_spawn_precheck_not_refused" in ids


def test_rejects_gem_adapter_precheck_if_adapter_claimed_implemented(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "gem_adapter_candidate")
    precheck["gem_adapter_implemented"] = True
    code, ids = _invalid_variant(tmp_path, payload, "gem-adapter-implemented")
    assert code != 0
    assert "gem_adapter_precheck_claims_adapter_implemented" in ids


def test_rejects_runner_precheck_if_runner_claimed_implemented_or_admitted(tmp_path: Path):
    for field in ("runner_implemented", "runner_admitted"):
        payload = _load(EXAMPLE)
        precheck = _precheck(payload, "runner_candidate")
        precheck[field] = True
        code, ids = _invalid_variant(tmp_path, payload, f"runner-{field}")
        assert code != 0
        assert "runner_precheck_claims_runner_available" in ids


def test_rejects_unsafe_precheck_if_not_refused(tmp_path: Path):
    payload = _load(EXAMPLE)
    precheck = _precheck(payload, "unsafe_command")
    precheck["result"] = "blocked"
    code, ids = _invalid_variant(tmp_path, payload, "unsafe-not-refused")
    assert code != 0
    assert "unsafe_precheck_not_refused" in ids


REQUIRED_FUTURE_ROUTING = {
    "command-pack validator": "missing_required_future_routing",
    "candidate-specific admission": "missing_required_future_routing",
    "runner interface contract": "missing_required_future_routing",
    "sandbox boundary contract": "missing_required_future_routing",
    "receipt contract": "missing_required_future_routing",
    "safety verifier": "missing_required_future_routing",
    "proof flow": "missing_required_future_routing",
    "production-readiness gate": "missing_required_future_routing",
}


def test_rejects_required_future_routing_missing_required_gate(tmp_path: Path):
    for gate, finding_id in REQUIRED_FUTURE_ROUTING.items():
        payload = _load(EXAMPLE)
        payload["required_future_routing"] = [
            item for item in payload["required_future_routing"] if item != gate
        ]
        code, ids = _invalid_variant(tmp_path, payload, f"missing-{gate.replace(' ', '-')}")
        assert code != 0
        assert finding_id in ids


REQUIRED_REFUSED_CATEGORIES = [
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
]


def test_rejects_refused_command_categories_missing_required_category(tmp_path: Path):
    for category in REQUIRED_REFUSED_CATEGORIES:
        payload = _load(EXAMPLE)
        payload["refused_command_categories"] = [
            item for item in payload["refused_command_categories"] if item != category
        ]
        code, ids = _invalid_variant(tmp_path, payload, f"missing-{category}")
        assert code != 0
        assert "missing_refused_command_category" in ids


REQUIRED_BLOCKED_CATEGORIES = [
    "runner_required_runner_unimplemented",
    "gem_adapter_required_adapter_unimplemented",
    "dry_run_required_candidate_unadmitted",
    "receipt_required_receipt_unissued",
    "publication_required_publication_unadmitted",
    "production_ready_required_not_claimed",
]


def test_rejects_blocked_command_categories_missing_required_category(tmp_path: Path):
    for category in REQUIRED_BLOCKED_CATEGORIES:
        payload = _load(EXAMPLE)
        payload["blocked_command_categories"] = [
            item for item in payload["blocked_command_categories"] if item != category
        ]
        code, ids = _invalid_variant(tmp_path, payload, f"missing-{category}")
        assert code != 0
        assert "missing_blocked_command_category" in ids


def test_existing_command_pack_validator_still_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "tools"
                / "execution-admission"
                / "validate_natural_language_o3de_command_pack.py"
            ),
            str(
                REPO_ROOT
                / "examples"
                / "execution-admission"
                / "natural_language_o3de_command_pack_v1.json"
            ),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"


def test_existing_pr_92_audit_and_supersession_validators_still_pass():
    validators = [
        (
            "validate_pr_92_natural_language_command_pack_audit.py",
            "pr_92_natural_language_command_pack_audit_v1.json",
        ),
        ("validate_pr_92_supersession_record.py", "pr_92_supersession_record_v1.json"),
    ]
    for validator_name, example_name in validators:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "execution-admission" / validator_name),
                str(REPO_ROOT / "examples" / "execution-admission" / example_name),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["status"] == "pass"


def test_existing_safety_verifier_still_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "audit" / "verify_sandbox_writer_safety.py"),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PASS:" in result.stdout
