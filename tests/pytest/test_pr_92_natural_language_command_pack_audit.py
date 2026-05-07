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
    / "validate_pr_92_natural_language_command_pack_audit.py"
)
EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "pr_92_natural_language_command_pack_audit_v1.json"
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


def _make_merge_safe_candidate(payload: dict) -> dict:
    out = copy.deepcopy(payload)
    out["audit_status"] = "audit_complete_merge_safe_if_static_only"
    out["merge_recommendation"] = "safe_to_merge_after_follow_up"
    out["unsafe_claims_detected"] = False
    for row in out["strict_acceptance_criteria"]:
        row["pass"] = True
    out["execution_surface_findings"]["direct_o3de_execution_detected"] = False
    out["runner_surface_findings"]["runner_implementation_detected"] = False
    out["gem_surface_findings"]["gem_adapter_implementation_detected"] = False
    out["admission_surface_findings"]["command_admission_detected"] = False
    out["publication_surface_findings"]["publication_admission_claim_detected"] = False
    out["production_readiness_surface_findings"]["production_ready_claim_detected"] = False
    return out


def test_valid_audit_report_validates():
    code, report = _run(EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"


def test_rejects_missing_pr_identity(tmp_path: Path):
    payload = _load(EXAMPLE)
    del payload["audited_pr"]["repo"]
    path = tmp_path / "missing-pr-identity.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "missing_pr_identity_fields" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_missing_changed_files_summary(tmp_path: Path):
    payload = _load(EXAMPLE)
    del payload["changed_files_summary"]
    path = tmp_path / "missing-changed-files-summary.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "missing_changed_files_summary" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_missing_merge_recommendation(tmp_path: Path):
    payload = _load(EXAMPLE)
    del payload["merge_recommendation"]
    path = tmp_path / "missing-merge-recommendation.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "missing_merge_recommendation" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_without_complete_strict_criteria(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    payload["strict_acceptance_criteria"].pop()
    path = tmp_path / "merge-safe-without-criteria.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "merge_safe_without_all_strict_criteria_passing" in _finding_ids(report) or "strict_acceptance_criteria_incomplete" in _finding_ids(report)


def test_rejects_merge_safe_when_direct_execution_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["execution_surface_findings"]["direct_o3de_execution_detected"]
    path = tmp_path / "merge-safe-missing-direct-execution-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "execution_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_runner_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["runner_surface_findings"]["runner_implementation_detected"]
    path = tmp_path / "merge-safe-missing-runner-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "runner_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_gem_adapter_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["gem_surface_findings"]["gem_adapter_implementation_detected"]
    path = tmp_path / "merge-safe-missing-gem-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "gem_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_admission_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["admission_surface_findings"]["command_admission_detected"]
    path = tmp_path / "merge-safe-missing-admission-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "admission_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_publication_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["publication_surface_findings"]["publication_admission_claim_detected"]
    path = tmp_path / "merge-safe-missing-publication-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "publication_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_production_ready_finding_missing(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    del payload["production_readiness_surface_findings"]["production_ready_claim_detected"]
    path = tmp_path / "merge-safe-missing-production-ready-finding.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "production_readiness_surface_findings_missing_keys" in _finding_ids(report) or "schema_validation_error" in _finding_ids(report)


def test_rejects_merge_safe_when_unsafe_claims_detected_true(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    payload["unsafe_claims_detected"] = True
    path = tmp_path / "merge-safe-unsafe-claims-true.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    assert "unsafe_claims_with_merge_safe_recommendation" in _finding_ids(report)


def test_rejects_inconclusive_with_merge_safe_recommendation(tmp_path: Path):
    payload = _make_merge_safe_candidate(_load(EXAMPLE))
    payload["audit_status"] = "audit_inconclusive"
    path = tmp_path / "inconclusive-merge-safe.json"
    _write(path, payload)
    code, report = _run(path)
    assert code != 0
    ids = _finding_ids(report)
    assert "merge_safe_status_mismatch" in ids or "incompatible_inconclusive_or_unsafe_merge_recommendation" in ids
