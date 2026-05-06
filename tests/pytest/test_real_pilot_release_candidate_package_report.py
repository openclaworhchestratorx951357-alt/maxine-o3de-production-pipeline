import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "tools"
    / "real-pilot-release-candidate-package"
    / "validate_real_pilot_release_candidate_package_report.py"
)
PASS_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-real-pilot-release-candidate-package-pass.manifest.json"
)
WARN_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-real-pilot-release-candidate-package-warn.manifest.json"
)
FAIL_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "example-real-pilot-release-candidate-package-fail.manifest.json"
)


def _run(manifest_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(manifest_path), *extra],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _parse_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"expected JSON output, got: {stdout}"
    return json.loads(stdout[start:])


def test_pass_manifest_returns_pass_and_exit_zero():
    result = _run(PASS_MANIFEST)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["release_candidate_status"] == "pass"
    assert payload["missing_required_gate_refs"] == []


def test_warn_manifest_returns_nonzero_without_allow_warn():
    result = _run(WARN_MANIFEST)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "warn"
    assert any(item.get("id") == "required_gate_warn_result" for item in payload["findings"])


def test_warn_manifest_returns_zero_with_allow_warn():
    result = _run(WARN_MANIFEST, "--allow-warn")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_manifest_returns_fail_and_nonzero():
    result = _run(FAIL_MANIFEST)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "false_admission_detected" in ids


def test_missing_required_gate_ref_fails(tmp_path: Path):
    manifest = json.loads(PASS_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["qc"]["gates"] = [
        gate for gate in manifest["qc"]["gates"] if gate.get("check_id") != "source_product_evidence_resolver_v1"
    ]
    tmp_manifest = tmp_path / "missing-required-gate.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "source_product_evidence_resolver_v1" in payload["missing_required_gate_refs"]


def test_insufficient_core_evidence_class_fails(tmp_path: Path):
    manifest = json.loads(PASS_MANIFEST.read_text(encoding="utf-8-sig"))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "dcc_conform_v1":
            gate.setdefault("details", {})
            gate["details"]["evidence_class"] = "fixture"
            break
    tmp_manifest = tmp_path / "core-evidence-class-fail.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "core_gate_evidence_class_insufficient" in ids


def test_output_is_manifest_attachable():
    result = _run(PASS_MANIFEST)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _parse_payload(result.stdout)
    attachment = payload["manifest_attachment"]
    assert attachment["target_path"] == "qc.gates[]"
    assert attachment["future_target_path"] == "qc.checks[]"
    assert attachment["qc_check"]["check_id"] == "real_pilot_release_candidate_package_v1"
