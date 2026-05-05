import json
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_ps(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_manifest_v1_golden_samples_validate():
    repo = _repo_root()
    validator = repo / "tools" / "manifest-validator" / "validate_manifest.py"
    samples = [
        repo / "examples" / "manifests" / "example-manifest-v1-success.json",
        repo / "examples" / "manifests" / "example-manifest-v1-failure.json",
        repo / "examples" / "manifests" / "example-manifest-v1-pending-manual.json",
    ]
    for sample in samples:
        result = subprocess.run(
            ["python", str(validator), str(sample)],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_manifest_writer_creates_required_fields_and_layout(tmp_path: Path):
    job_id = "pytest-manifest-v1-create"
    artifact_root = tmp_path / "artifacts" / "jobs" / job_id
    manifest_path = artifact_root / "manifest.json"
    cmd = (
        "& ./scripts/powershell/New-MaxineManifest.ps1 "
        f"-JobId '{job_id}' "
        "-Lane 'draft_mesh' "
        "-CharacterName 'Pytest Character' "
        "-Operator 'ci' "
        f"-ArtifactRoot '{artifact_root}' "
        f"-OutputPath '{manifest_path}' | Out-Null"
    )
    result = _run_ps(cmd)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    data = _read_json(manifest_path)
    assert data["schema_version"] == "1.0.0"
    assert data["job"]["status"] == "created"
    assert data["job"]["lane"] == "draft_mesh"
    assert data["evidence"]["artifact_root"] == str(artifact_root)
    assert data["manual_review"]["review_state"] == "not_required"
    assert data["qc"]["overall"] == "not_run"
    for folder in ("logs", "screenshots", "o3de", "qc", "temp", "undo", "cleanup"):
        assert (artifact_root / folder).exists()


def test_manifest_failed_update_records_error_and_cleanup(tmp_path: Path):
    job_id = "pytest-manifest-v1-fail"
    artifact_root = tmp_path / "artifacts" / "jobs" / job_id
    manifest_path = artifact_root / "manifest.json"

    create_cmd = (
        "& ./scripts/powershell/New-MaxineManifest.ps1 "
        f"-JobId '{job_id}' "
        "-Lane 'text_full_rig' "
        "-CharacterName 'Fail Character' "
        "-Operator 'ci' "
        f"-ArtifactRoot '{artifact_root}' "
        f"-OutputPath '{manifest_path}' | Out-Null"
    )
    assert _run_ps(create_cmd).returncode == 0

    update_cmd = (
        "& ./scripts/powershell/Write-MaxineEvidence.ps1 "
        f"-JobId '{job_id}' "
        f"-ManifestPath '{manifest_path}' "
        f"-EvidenceRoot '{artifact_root}' "
        "-Status 'fail' "
        "-Message 'Synthetic stage failure.' "
        "-ExitCode 2 "
        "-ErrorCode 'SYNTHETIC_STAGE_FAILURE' "
        "-ErrorStage 'generation' | Out-Null"
    )
    result = _run_ps(update_cmd)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    data = _read_json(manifest_path)
    assert data["job"]["status"] == "fail"
    assert data["job"]["finished_at"] is not None
    assert data["qc"]["overall"] == "fail"
    assert data["errors"], "Expected at least one structured error"
    assert data["errors"][-1]["code"] == "SYNTHETIC_STAGE_FAILURE"
    assert data["errors"][-1]["stage"] == "generation"
    cleanup_paths = set(data["cleanup"]["paths"])
    assert str(artifact_root / "temp") in cleanup_paths
    assert str(artifact_root / "cleanup") in cleanup_paths


def test_manifest_pending_manual_support(tmp_path: Path):
    job_id = "pytest-manifest-v1-manual"
    artifact_root = tmp_path / "artifacts" / "jobs" / job_id
    manifest_path = artifact_root / "manifest.json"

    create_cmd = (
        "& ./scripts/powershell/New-MaxineManifest.ps1 "
        f"-JobId '{job_id}' "
        "-Lane 'release_character' "
        "-CharacterName 'Manual Character' "
        "-Operator 'human' "
        f"-ArtifactRoot '{artifact_root}' "
        f"-OutputPath '{manifest_path}' | Out-Null"
    )
    assert _run_ps(create_cmd).returncode == 0

    update_cmd = (
        "& ./scripts/powershell/Write-MaxineEvidence.ps1 "
        f"-JobId '{job_id}' "
        f"-ManifestPath '{manifest_path}' "
        f"-EvidenceRoot '{artifact_root}' "
        "-Status 'pending_manual' "
        "-Message 'Manual release review is required.' "
        "-ManualReviewReason 'Operator approval pending.' | Out-Null"
    )
    result = _run_ps(update_cmd)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    data = _read_json(manifest_path)
    assert data["job"]["status"] == "pending_manual"
    assert data["manual_review"]["required"] is True
    assert data["manual_review"]["review_state"] == "pending"
    assert data["manual_review"]["reason"] == "Operator approval pending."


def test_manifest_unknown_fields_preserved_on_update(tmp_path: Path):
    job_id = "pytest-manifest-v1-forward-compat"
    artifact_root = tmp_path / "artifacts" / "jobs" / job_id
    manifest_path = artifact_root / "manifest.json"
    create_cmd = (
        "& ./scripts/powershell/New-MaxineManifest.ps1 "
        f"-JobId '{job_id}' "
        "-Lane 'text_mesh' "
        "-CharacterName 'Compat Character' "
        "-Operator 'ci' "
        f"-ArtifactRoot '{artifact_root}' "
        f"-OutputPath '{manifest_path}' | Out-Null"
    )
    assert _run_ps(create_cmd).returncode == 0

    data = _read_json(manifest_path)
    data["future_extension"] = {"reserved": True, "value": 17}
    data["job"]["future_job_flag"] = "forward-safe"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    update_cmd = (
        "& ./scripts/powershell/Write-MaxineEvidence.ps1 "
        f"-JobId '{job_id}' "
        f"-ManifestPath '{manifest_path}' "
        f"-EvidenceRoot '{artifact_root}' "
        "-Status 'running' "
        "-Message 'Compatibility update.' | Out-Null"
    )
    result = _run_ps(update_cmd)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    updated = _read_json(manifest_path)
    assert updated["future_extension"]["reserved"] is True
    assert updated["job"]["future_job_flag"] == "forward-safe"


def test_manifest_status_values_are_restricted():
    cmd = (
        "& ./scripts/powershell/New-MaxineManifest.ps1 "
        "-JobId 'pytest-manifest-v1-invalid' "
        "-Lane 'draft_mesh' "
        "-Status 'impossible' "
        "-CharacterName 'Invalid' "
    )
    result = _run_ps(cmd)
    assert result.returncode != 0
