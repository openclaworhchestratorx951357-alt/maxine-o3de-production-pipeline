import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "skeleton-validator" / "validate_skeleton_contract.py"


def _contract_path() -> Path:
    return _repo_root() / "examples" / "skeleton-contracts" / "MAX_BIPED_v1.json"


def _skeleton_path(name: str) -> Path:
    return _repo_root() / "examples" / "skeletons" / name


def _run_validator(skeleton_path: Path, allow_warn: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_validator_script()), str(_contract_path()), str(skeleton_path)]
    if allow_warn:
        cmd.append("--allow-warn")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"Validator stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


def test_passing_skeleton_returns_pass():
    result = _run_validator(_skeleton_path("max_biped_v1_pass.json"))
    assert result.returncode == 0, f"Unexpected validator failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warning_skeleton_returns_warn_and_allow_warn_controls_exit():
    strict = _run_validator(_skeleton_path("max_biped_v1_warn.json"), allow_warn=False)
    assert strict.returncode != 0, "Warn status should return nonzero without --allow-warn"
    strict_payload = _extract_payload(strict.stdout)
    assert strict_payload["status"] == "warn"

    allowed = _run_validator(_skeleton_path("max_biped_v1_warn.json"), allow_warn=True)
    assert allowed.returncode == 0, f"Warn status should pass with --allow-warn:\n{allowed.stdout}\n{allowed.stderr}"
    allowed_payload = _extract_payload(allowed.stdout)
    assert allowed_payload["status"] == "warn"


def test_failing_skeleton_returns_fail():
    result = _run_validator(_skeleton_path("max_biped_v1_fail.json"))
    assert result.returncode != 0, "Fail status must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_root_bone_fails(tmp_path: Path):
    skeleton = json.loads(_skeleton_path("max_biped_v1_pass.json").read_text(encoding="utf-8-sig"))
    skeleton["skeleton_id"] = "missing-root"
    skeleton["bones"] = [b for b in skeleton["bones"] if b.get("name") != "root"]
    test_file = tmp_path / "missing-root.json"
    test_file.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(f.get("rule_id") == "root_bone_required" for f in payload["findings"])


def test_missing_pelvis_parent_relationship_fails(tmp_path: Path):
    skeleton = json.loads(_skeleton_path("max_biped_v1_pass.json").read_text(encoding="utf-8-sig"))
    skeleton["skeleton_id"] = "pelvis-parent-mismatch"
    for bone in skeleton["bones"]:
        if bone.get("name") == "pelvis":
            bone["parent"] = "spine_01"
            break
    test_file = tmp_path / "pelvis-parent-mismatch.json"
    test_file.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(f.get("rule_id") == "pelvis_parent_mismatch" for f in payload["findings"])


def test_left_right_optional_mismatch_warns(tmp_path: Path):
    skeleton = json.loads(_skeleton_path("max_biped_v1_pass.json").read_text(encoding="utf-8-sig"))
    skeleton["skeleton_id"] = "optional-mirror-warn"
    skeleton["bones"] = [b for b in skeleton["bones"] if b.get("name") != "lowerarm_twist_01_r"]
    test_file = tmp_path / "optional-mirror-warn.json"
    test_file.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")

    result = _run_validator(test_file, allow_warn=False)
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"
    assert any(f.get("rule_id") == "optional_mirror_pair_missing" for f in payload["findings"])


def test_validator_output_has_manifest_attachable_qc_fields():
    result = _run_validator(_skeleton_path("max_biped_v1_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})

    assert "target_path" in attachment
    assert "future_target_path" in attachment
    assert attachment["target_path"] == "qc.gates[]"
    assert attachment["future_target_path"] == "qc.checks[]"
    assert qc_check.get("check_id") == "max_biped_v1_skeleton_contract"
    assert qc_check.get("result") == "pass"
