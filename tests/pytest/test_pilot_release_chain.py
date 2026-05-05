import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "release-lane" / "validate_pilot_release_chain.py"


def _manifest_fixture() -> Path:
    return _repo_root() / "examples" / "manifests" / "example-release-character-pilot-chain.manifest.json"


def _chain_fixture() -> Path:
    return _repo_root() / "examples" / "release-lane-gate-chain" / "max_biped_v1_release_lane_gate_chain.json"


def _run(manifest: Path, chain: Path, allow_warn: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_validator_script()), str(manifest), "--chain", str(chain)]
    if allow_warn:
        cmd.append("--allow-warn")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"Validator output did not contain JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


def test_pilot_manifest_warn_without_allow_warn():
    result = _run(_manifest_fixture(), _chain_fixture(), allow_warn=False)
    payload = _payload(result.stdout)
    assert payload["status"] == "warn"
    assert result.returncode != 0


def test_pilot_manifest_warn_with_allow_warn_exit_zero():
    result = _run(_manifest_fixture(), _chain_fixture(), allow_warn=True)
    payload = _payload(result.stdout)
    assert payload["status"] == "warn"
    assert result.returncode == 0


def test_missing_required_gate_fails(tmp_path: Path):
    manifest = json.loads(_manifest_fixture().read_text(encoding="utf-8-sig"))
    manifest["qc"]["gates"] = [
        item
        for item in manifest["qc"]["gates"]
        if item.get("check_id") != "release_publication_gate_set_v1"
    ]
    path = tmp_path / "missing-gate.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(path, _chain_fixture())
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_gate_missing" for item in payload["findings"])


def test_out_of_order_gate_fails(tmp_path: Path):
    manifest = json.loads(_manifest_fixture().read_text(encoding="utf-8-sig"))
    gates = manifest["qc"]["gates"]
    gates[0], gates[1] = gates[1], gates[0]
    path = tmp_path / "out-of-order.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(path, _chain_fixture())
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_gate_out_of_order" for item in payload["findings"])


def test_duplicate_check_id_fails(tmp_path: Path):
    manifest = json.loads(_manifest_fixture().read_text(encoding="utf-8-sig"))
    manifest["qc"]["gates"].append(dict(manifest["qc"]["gates"][0]))
    path = tmp_path / "duplicate-check-id.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(path, _chain_fixture())
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item.get("id") == "duplicate_check_id" for item in payload["findings"])


def test_unimplemented_gate_marked_pass_fails(tmp_path: Path):
    manifest = json.loads(_manifest_fixture().read_text(encoding="utf-8-sig"))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "ci_artifact_retention_v1":
            gate["result"] = "pass"
            gate["severity"] = "info"
            break
    path = tmp_path / "unimplemented-pass.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(path, _chain_fixture())
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item.get("id") == "unimplemented_gate_marked_pass" for item in payload["findings"])


def test_implemented_rollback_or_readiness_gate_pending_manual_fails(tmp_path: Path):
    manifest = json.loads(_manifest_fixture().read_text(encoding="utf-8-sig"))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "release_publication_rollback_drill_v1":
            gate["result"] = "pending_manual"
            gate["severity"] = "manual_review"
            break
    path = tmp_path / "implemented-pending-manual.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(path, _chain_fixture())
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item.get("id") == "implemented_gate_pending_manual" for item in payload["findings"])


def test_output_contains_manifest_attachable_payload():
    result = _run(_manifest_fixture(), _chain_fixture(), allow_warn=True)
    payload = _payload(result.stdout)

    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert attachment.get("target_path") == "qc.gates[]"
    assert attachment.get("future_target_path") == "qc.checks[]"
    assert qc_check.get("check_id") == "pilot_release_chain_v1"
