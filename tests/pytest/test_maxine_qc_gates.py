import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "qc" / "run_qc.py"
DRAFT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "draft_mesh.pass.example.json"
RELEASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"


def _run(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(path), *extra],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )


def _parse(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, stdout
    return json.loads(stdout[start:])


def _copy_manifest(tmp_path: Path, source: Path) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    target = tmp_path / source.name
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def test_known_good_draft_passes():
    result = _run(DRAFT_MANIFEST, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _parse(result.stdout)["status"] == "pass"


def test_known_good_release_passes_using_fixtures():
    result = _run(RELEASE_MANIFEST, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _parse(result.stdout)["status"] == "pass"


def test_release_missing_actor_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, RELEASE_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["o3de"]["actual_products"] = [
        product for product in payload["o3de"]["actual_products"] if product["product_type"] != "actor"
    ]
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    payload = _parse(result.stdout)
    assert "MXN_ASSET_PRODUCT_MISSING" in payload["error_codes"]


def test_release_missing_undo_plan_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, RELEASE_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["undo"] = {}
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    assert "MXN_UNDO_PLAN_MISSING" in _parse(result.stdout)["error_codes"]


def test_release_missing_provenance_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, RELEASE_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["provenance"] = {}
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    assert "MXN_PROVENANCE_INCOMPLETE" in _parse(result.stdout)["error_codes"]


def test_hero_missing_facial_morph_inventory_fails(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, RELEASE_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["identity"]["character_tier"] = "hero"
    payload["dcc_conform"]["facial"] = {"morphs": []}
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict")

    assert result.returncode != 0
    assert "MXN_FACIAL_MORPH_MISSING" in _parse(result.stdout)["error_codes"]


def test_npc_missing_facial_morph_inventory_warns(tmp_path: Path):
    manifest_path = _copy_manifest(tmp_path, RELEASE_MANIFEST)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["identity"]["character_tier"] = "npc"
    payload["dcc_conform"]["facial"] = {"morphs": [], "waiver": {"approved": True}}
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(manifest_path, "--strict", "--allow-warn")
    payload = _parse(result.stdout)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "warn"
    assert "MXN_FACIAL_MORPH_MISSING" in payload["warning_codes"]
