import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_discovery_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    discovery_script = repo_root / "tools" / "asset-resolver" / "discover_ap_metadata_sources.py"
    assert discovery_script.exists()


def test_discovery_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_script = repo_root / "scripts" / "powershell" / "Find-MaxineApMetadata.ps1"
    assert wrapper_script.exists()


def test_discovery_candidates_file_exists():
    repo_root = Path(__file__).resolve().parents[2]
    candidates_file = repo_root / "tools" / "asset-resolver" / "ap_metadata_candidates.json"
    assert candidates_file.exists()


def test_discovery_records_expected_metadata(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    discovery_script = repo_root / "tools" / "asset-resolver" / "discover_ap_metadata_sources.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"

    fake_project = tmp_path / "fake-project"
    (fake_project / "user").mkdir(parents=True, exist_ok=True)
    (fake_project / "Registry").mkdir(parents=True, exist_ok=True)
    (fake_project / "user" / "log").mkdir(parents=True, exist_ok=True)
    (fake_project / "Cache" / "pc").mkdir(parents=True, exist_ok=True)

    (fake_project / "project.json").write_text(
        json.dumps(
            {
                "project_name": "FakeMaxineProject",
                "engine": "o3de",
                "external_subdirectories": ["Gems/FakeGem"],
            }
        ),
        encoding="utf-8",
    )
    (fake_project / "user" / "project.json").write_text(
        json.dumps({"user_setting": True}),
        encoding="utf-8",
    )
    (fake_project / "Registry" / "test.setreg").write_text("{}", encoding="utf-8")
    (fake_project / "user" / "log" / "AssetProcessor.log").write_text("log", encoding="utf-8")
    (fake_project / "Cache" / "pc" / "assetdb.sqlite").write_text("not-a-real-db", encoding="utf-8")

    manifest_in = tmp_path / "input.manifest.json"
    manifest_out = tmp_path / "output.manifest.json"
    shutil.copy2(manifest_src, manifest_in)

    cmd = [
        sys.executable,
        str(discovery_script),
        "--manifest",
        str(manifest_in),
        "--project-path",
        str(fake_project),
        "--output",
        str(manifest_out),
        "--include-hashes",
        "true",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Discovery failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    discovery = data.get("o3de", {}).get("ap_metadata_discovery")
    assert isinstance(discovery, dict), "o3de.ap_metadata_discovery missing"
    assert discovery.get("project_exists") is True
    assert discovery.get("project_json", {}).get("exists") is True
    assert discovery.get("project_json", {}).get("parsed_project_name") == "FakeMaxineProject"
    assert discovery.get("user_project_json", {}).get("exists") is True
    assert len(discovery.get("settings_registry_files", [])) >= 1
    assert discovery.get("summary", {}).get("existing_log_count", 0) >= 1
    assert discovery.get("summary", {}).get("existing_database_candidate_count", 0) >= 1

    safety = discovery.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("ran_o3de_editor") is False
    assert safety.get("ran_asset_processor") is False
    assert safety.get("modified_project") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("real_o3de_query_used") is False
    assert safety.get("cache_guessing_used_as_success") is False
