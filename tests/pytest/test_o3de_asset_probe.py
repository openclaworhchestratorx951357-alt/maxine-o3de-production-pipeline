import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_probe_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    probe_script = repo_root / "tools" / "asset-resolver" / "probe_o3de_asset_filesystem.py"
    assert probe_script.exists()


def test_probe_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_script = repo_root / "scripts" / "powershell" / "Probe-MaxineO3deAsset.ps1"
    assert wrapper_script.exists()


def test_probe_records_project_and_source_evidence(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    probe_script = repo_root / "tools" / "asset-resolver" / "probe_o3de_asset_filesystem.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"

    manifest_in = tmp_path / "probe-input.manifest.json"
    manifest_out = tmp_path / "probe-output.manifest.json"
    shutil.copy2(manifest_src, manifest_in)

    fake_project = tmp_path / "fake-project"
    source_asset_rel = Path("Assets/Characters/Test/source/test.obj")
    source_asset_abs = fake_project / source_asset_rel
    source_asset_abs.parent.mkdir(parents=True, exist_ok=True)
    source_asset_abs.write_text("probe test asset", encoding="utf-8")
    (fake_project / "project.json").write_text('{"project_name":"ProbeTest"}', encoding="utf-8")

    cmd = [
        sys.executable,
        str(probe_script),
        "--manifest",
        str(manifest_in),
        "--source-asset",
        str(source_asset_rel).replace("\\", "/"),
        "--project-path",
        str(fake_project),
        "--output",
        str(manifest_out),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Probe failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    probe = data.get("o3de", {}).get("asset_probe")
    assert isinstance(probe, dict), "o3de.asset_probe missing"
    assert probe.get("project_exists") is True
    assert probe.get("project_json_exists") is True
    assert probe.get("source_asset_exists") is True
    assert probe.get("cache_guessing_used") is False
    assert probe.get("real_o3de_query_used") is False
    assert probe.get("authoritative_resolution") is False
    sha256_hex = probe.get("sha256", "")
    assert isinstance(sha256_hex, str) and len(sha256_hex) == 64
