import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "release-lane" / "report_release_lane_evidence_admission_status.py"
MANIFEST = REPO_ROOT / "examples" / "manifests" / "example-release-character-pilot-chain.manifest.json"


def run_cmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def test_report_default_manifest_outputs_controlled_evidence_ready_execution_blocked_status():
    result = run_cmd("--manifest", str(MANIFEST))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["status"] == "pass"
    assert payload["report_type"] == "RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT"
    assert payload["manifest_attachment_target_path"] == "qc.gates[]"
    assert payload["future_manifest_attachment_target_path"] == "qc.checks[]"
    assert payload["overall_release_lane_state"] == "controlled_evidence_ready_execution_blocked"

    evidence = payload["evidence_classification"]
    assert "source_product_evidence_resolver_v1" in evidence["imported_check_ids"]
    assert "manual_hero_review_v1" in evidence["manual_check_ids"]
    assert "screenshot_evidence_v1" in evidence["fixture_check_ids"]
    assert "max_biped_v1_skeleton_contract" in evidence["controlled_real_check_ids"]
    assert "dcc_conform_v1" in evidence["controlled_real_check_ids"]

    execution = payload["execution_admission_status"]
    assert execution["execution_admitted"] is False
    assert "o3de_editor_execution" in execution["blocked_surfaces"]

    missing = payload["missing_for_operational"]
    assert not any("controlled real evidence" in item for item in missing)
    assert any("execution-admission decision" in item for item in missing)


def test_report_can_write_output_file(tmp_path: Path):
    output_path = tmp_path / "status.json"
    result = run_cmd("--manifest", str(MANIFEST), "--output", str(output_path))
    assert result.returncode == 0, result.stderr
    assert output_path.exists()

    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)
    assert file_payload["report_type"] == stdout_payload["report_type"]
    assert file_payload["manifest_path"] == stdout_payload["manifest_path"]


def test_report_fails_for_missing_manifest():
    result = run_cmd("--manifest", "examples/manifests/does-not-exist.json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert payload["error"] == "manifest_not_found"
