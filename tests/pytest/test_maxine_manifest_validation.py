import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "validation" / "validate_manifests.py"
PASS_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"
MIXAMO_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "external_rig_import.pending_manual.example.json"
)


def _run(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *extra],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )


def _copy_manifest(tmp_path: Path, source: Path) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    target = tmp_path / source.name
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def test_valid_release_manifest_passes_schema_and_strict_evidence():
    result = _run(PASS_MANIFEST, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_missing_required_manifest_field_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, PASS_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.pop("provenance")
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path)

    assert result.returncode != 0
    assert "provenance" in result.stdout


def test_bad_manifest_status_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, PASS_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["job"]["status"] = "complete"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path)

    assert result.returncode != 0
    assert "status" in result.stdout


def test_missing_evidence_ref_fails_in_strict_mode(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, PASS_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["evidence"]["refs"][0]["path"] = "examples/production/missing-evidence.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    assert "MXN_INPUT_MISSING" in result.stdout


def test_mixamo_pending_manual_manifest_is_valid():
    result = _run(MIXAMO_MANIFEST, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pending_manual" in result.stdout


def test_cache_heuristic_marker_fails_release_manifest(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, PASS_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["o3de"]["product_resolution"]["cache_heuristic_used"] = True
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.stdout
