import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "tools" / "manifest-validator" / "attach_qc_gate.py"


def _base_manifest() -> Path:
    return _repo_root() / "examples" / "manifests" / "example-release-character-qc-attach-base.manifest.json"


def _attachment(name: str) -> Path:
    return _repo_root() / "examples" / "manifest-qc-attachments" / name


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_script_path()), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _copy_manifest_to_tmp(tmp_path: Path, name: str = "manifest.json") -> Path:
    target = tmp_path / name
    shutil.copyfile(_base_manifest(), target)
    return target


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "manifests" / "_pytest_manifest_qc_attach"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_attach_single_pass_payload_updates_gates_and_preserves_unknown_fields(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "pass-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert data["qc"]["overall"] == "pass"
    assert len(data["qc"]["gates"]) == 1
    assert data["qc"]["gates"][0]["check_id"] == "max_biped_v1_skeleton_contract"
    assert data["x_unknown_extension_for_forward_compatibility"]["preserve_me"] is True
    assert list(manifest.parent.glob(".manifest-qc-attach-*.tmp")) == []


def test_attach_warn_payload_sets_qc_overall_warn(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "warn-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_dcc_conform_attach_warn.json")),
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert data["qc"]["overall"] == "warn"
    assert len(data["qc"]["gates"]) == 1
    assert data["qc"]["gates"][0]["result"] == "warn"


def test_attach_fail_payload_sets_qc_overall_fail(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "fail-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_source_product_attach_fail.json")),
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert data["qc"]["overall"] == "fail"
    assert len(data["qc"]["gates"]) == 1
    assert data["qc"]["gates"][0]["check_id"] == "source_product_evidence_resolver_v1"


def test_attach_multiple_payloads_derives_overall_fail(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "multi-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
            "--attachment",
            str(_attachment("max_biped_v1_dcc_conform_attach_warn.json")),
            "--attachment",
            str(_attachment("max_biped_v1_source_product_attach_fail.json")),
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert data["qc"]["overall"] == "fail"
    assert len(data["qc"]["gates"]) == 3


def test_duplicate_check_id_fails_by_default(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "duplicate-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
        ]
    )
    assert result.returncode != 0
    assert "duplicate check_id" in (result.stdout + result.stderr).lower()


def test_duplicate_check_id_can_be_allowed(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "duplicate-allowed-manifest.json")
    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
            "--allow-duplicate-check-id",
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert len(data["qc"]["gates"]) == 2


def test_malformed_attachment_fails(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "malformed-manifest.json")
    malformed = repo_tmp_dir / "malformed-attachment.json"
    malformed.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(malformed),
        ]
    )
    assert result.returncode != 0
    assert "manifest_attachment" in (result.stdout + result.stderr)


def test_attachment_with_invalid_target_path_fails(repo_tmp_dir: Path):
    manifest = _copy_manifest_to_tmp(repo_tmp_dir, "invalid-target-manifest.json")
    invalid_attachment = repo_tmp_dir / "invalid-target-attachment.json"
    invalid_payload = json.loads(
        _attachment("max_biped_v1_skeleton_attach_pass.json").read_text(encoding="utf-8-sig")
    )
    invalid_payload["manifest_attachment"]["target_path"] = "qc.invalid[]"
    invalid_attachment.write_text(json.dumps(invalid_payload, indent=2), encoding="utf-8")

    result = _run(
        [
            "--manifest",
            str(manifest),
            "--attachment",
            str(invalid_attachment),
        ]
    )
    assert result.returncode != 0
    assert "target_path" in (result.stdout + result.stderr)


def test_outside_repo_manifest_path_is_blocked(tmp_path: Path):
    outside_manifest = tmp_path / "outside-manifest.json"
    outside_manifest.write_text("{}", encoding="utf-8")
    result = _run(
        [
            "--manifest",
            str(outside_manifest),
            "--attachment",
            str(_attachment("max_biped_v1_skeleton_attach_pass.json")),
        ]
    )
    assert result.returncode != 0
    assert "inside repository root" in (result.stdout + result.stderr)
