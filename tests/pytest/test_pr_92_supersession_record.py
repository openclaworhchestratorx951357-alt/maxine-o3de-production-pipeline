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
    / "validate_pr_92_supersession_record.py"
)
EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "pr_92_supersession_record_v1.json"
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
    )
    report = json.loads(result.stdout)
    return result.returncode, report


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


def test_valid_supersession_record_validates():
    code, report = _run(EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["superseded_pr_number"] == 92
    assert report["superseding_pr_number"] == 95
    assert report["audit_pr_number"] == 94


def test_rejects_superseded_pr_other_than_92(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["superseded_pr"]["pr_number"] = 91
    code, ids = _invalid_variant(tmp_path, payload, "wrong-superseded-pr")
    assert code != 0
    assert "wrong_superseded_pr" in ids or "schema_validation_error" in ids


def test_rejects_superseding_pr_other_than_95(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["superseding_pr"]["pr_number"] = 94
    code, ids = _invalid_variant(tmp_path, payload, "wrong-superseding-pr")
    assert code != 0
    assert "wrong_superseding_pr" in ids or "schema_validation_error" in ids


def test_rejects_audit_pr_other_than_94(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["audit_pr"]["pr_number"] = 95
    code, ids = _invalid_variant(tmp_path, payload, "wrong-audit-pr")
    assert code != 0
    assert "wrong_audit_pr" in ids or "schema_validation_error" in ids


def test_rejects_audit_merge_recommendation_other_than_do_not_merge_yet(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["audit_pr"]["merge_recommendation"] = "safe_to_merge_after_follow_up"
    code, ids = _invalid_variant(tmp_path, payload, "wrong-audit-merge-recommendation")
    assert code != 0
    assert "wrong_audit_merge_recommendation" in ids or "schema_validation_error" in ids


def test_rejects_pr_92_merge_allowed_true(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["pr_92_merge_allowed"] = True
    code, ids = _invalid_variant(tmp_path, payload, "merge-allowed")
    assert code != 0
    assert "pr_92_merge_allowed_true" in ids or "schema_validation_error" in ids


def test_rejects_pr_92_close_recommended_false(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["pr_92_close_recommended"] = False
    code, ids = _invalid_variant(tmp_path, payload, "close-not-recommended")
    assert code != 0
    assert "pr_92_close_not_recommended" in ids or "schema_validation_error" in ids


def test_rejects_empty_required_revision_conditions(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["required_revision_conditions"] = []
    code, ids = _invalid_variant(tmp_path, payload, "empty-revision-conditions")
    assert code != 0
    assert "missing_required_revision_conditions" in ids or "schema_validation_error" in ids


def test_rejects_empty_forbidden_interpretations(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["forbidden_interpretations"] = []
    code, ids = _invalid_variant(tmp_path, payload, "empty-forbidden-interpretations")
    assert code != 0
    assert "missing_forbidden_interpretations" in ids or "schema_validation_error" in ids


def test_rejects_empty_required_future_routing(tmp_path: Path):
    payload = _load(EXAMPLE)
    payload["required_future_routing"] = []
    code, ids = _invalid_variant(tmp_path, payload, "empty-future-routing")
    assert code != 0
    assert "missing_required_future_routing" in ids or "schema_validation_error" in ids


ROUTING_REQUIREMENTS = {
    "runner interface contract": "missing_runner_interface_routing",
    "sandbox boundary contract": "missing_sandbox_boundary_routing",
    "receipt contract": "missing_receipt_contract_routing",
    "safety verifier": "missing_safety_verifier_routing",
    "proof flow": "missing_proof_flow_routing",
    "production-readiness gate": "missing_production_readiness_gate_routing",
}


def test_required_future_routing_contains_all_required_gates():
    payload = _load(EXAMPLE)
    routing = set(payload["required_future_routing"])
    for required in {
        "command-pack validator",
        "candidate-specific admission",
        "runner interface contract",
        "sandbox boundary contract",
        "receipt contract",
        "safety verifier",
        "proof flow",
        "production-readiness gate",
    }:
        assert required in routing


def test_rejects_missing_required_future_routing_gate(tmp_path: Path):
    for gate, finding_id in ROUTING_REQUIREMENTS.items():
        payload = _load(EXAMPLE)
        payload["required_future_routing"] = [
            item for item in payload["required_future_routing"] if item != gate
        ]
        code, ids = _invalid_variant(
            tmp_path, payload, f"missing-{gate.replace(' ', '-')}"
        )
        assert code != 0
        assert finding_id in ids


SAFETY_FALSE_FIELDS = {
    "direct_o3de_execution": "direct_o3de_execution_allowed",
    "runner_implemented": "runner_implemented_true",
    "gem_adapter_implemented": "gem_adapter_implemented_true",
    "command_admitted": "command_admitted_true",
    "dry_run_admitted": "dry_run_admitted_true",
    "real_execution_admitted": "real_execution_admitted_true",
    "publication_admitted": "publication_admitted_true",
    "production_ready_claimed": "production_ready_claimed_true",
}


def test_rejects_any_protected_safety_posture_true(tmp_path: Path):
    for field, finding_id in SAFETY_FALSE_FIELDS.items():
        payload = _load(EXAMPLE)
        payload["safety_posture"][field] = True
        code, ids = _invalid_variant(tmp_path, payload, f"{field}-true")
        assert code != 0
        assert finding_id in ids or "schema_validation_error" in ids


def test_existing_pr_92_audit_validator_still_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "tools"
                / "execution-admission"
                / "validate_pr_92_natural_language_command_pack_audit.py"
            ),
            str(
                REPO_ROOT
                / "examples"
                / "execution-admission"
                / "pr_92_natural_language_command_pack_audit_v1.json"
            ),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"


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


def test_existing_runner_interface_validator_still_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "tools"
                / "execution-admission"
                / "validate_release_candidate_publication_dry_run_runner_interface.py"
            ),
            str(
                REPO_ROOT
                / "examples"
                / "execution-admission"
                / "release_candidate_package_publish_dry_run_runner_interface_v1.json"
            ),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"


def test_existing_sandbox_boundary_validator_still_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "tools"
                / "execution-admission"
                / "validate_release_candidate_publication_dry_run_sandbox_boundary.py"
            ),
            str(
                REPO_ROOT
                / "examples"
                / "execution-admission"
                / "release_candidate_package_publish_dry_run_sandbox_boundary_v1.json"
            ),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
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
