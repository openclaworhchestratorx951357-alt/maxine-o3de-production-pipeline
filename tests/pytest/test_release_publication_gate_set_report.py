import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "tools"
    / "release-publication-gate-set"
    / "validate_release_publication_gate_set_report.py"
)
PASS_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-release-publication-gate-set-pass.manifest.json"
)
WARN_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-release-publication-gate-set-warn.manifest.json"
)
FAIL_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-release-publication-gate-set-fail.manifest.json"
)


def _run(manifest_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(manifest_path), *extra],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _parse_report(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"expected JSON output, got: {stdout}"
    return json.loads(stdout[start:])


def test_pass_manifest_returns_pass_and_exit_zero():
    result = _run(PASS_MANIFEST)
    assert result.returncode == 0, result.stdout + result.stderr
    report = _parse_report(result.stdout)
    assert report["status"] == "pass"
    assert report["missing_required_gates"] == []
    assert report["out_of_order_gates"] == []


def test_warn_manifest_returns_nonzero_without_allow_warn():
    result = _run(WARN_MANIFEST)
    assert result.returncode != 0
    report = _parse_report(result.stdout)
    assert report["status"] == "warn"
    assert any(item.get("result") == "warn" for item in report["blocked_by_status"])


def test_warn_manifest_returns_zero_with_allow_warn():
    result = _run(WARN_MANIFEST, "--allow-warn")
    assert result.returncode == 0, result.stdout + result.stderr
    report = _parse_report(result.stdout)
    assert report["status"] == "warn"


def test_fail_manifest_returns_fail_and_nonzero():
    result = _run(FAIL_MANIFEST)
    assert result.returncode != 0
    report = _parse_report(result.stdout)
    assert report["status"] == "fail"
    assert "release_publication_execution_window_state_v1" in report["missing_required_gates"]
    assert any(item.get("check_id") == "release_publication_execution_admission_review_v1" for item in report["blocked_by_status"])


def test_hero_manifest_requires_manual_hero_review_gate(tmp_path: Path):
    manifest = json.loads(PASS_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["identity"]["tier"] = "hero"
    tmp_manifest = tmp_path / "hero-missing-manual.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    report = _parse_report(result.stdout)
    assert report["status"] == "fail"
    assert "manual_hero_review_v1" in report["missing_required_gates"]


def test_supports_legacy_gate_check_field(tmp_path: Path):
    manifest = json.loads(PASS_MANIFEST.read_text(encoding="utf-8-sig"))
    first = manifest["qc"]["gates"][0]
    first["check"] = first["check_id"]
    del first["check_id"]
    tmp_manifest = tmp_path / "legacy-check-field.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode == 0, result.stdout + result.stderr
    report = _parse_report(result.stdout)
    assert report["status"] == "pass"


def test_report_output_is_manifest_attachable():
    result = _run(PASS_MANIFEST)
    assert result.returncode == 0, result.stdout + result.stderr
    report = _parse_report(result.stdout)
    attachment = report["manifest_attachment"]
    assert attachment["target_path"] == "qc.gates[]"
    assert attachment["future_target_path"] == "qc.checks[]"
    assert attachment["qc_check"]["check_id"] == "release_publication_gate_set_v1"
