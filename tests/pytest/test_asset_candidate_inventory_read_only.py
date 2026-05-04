import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_INVENTORY_READ_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineProjectInventoryRead.ps1"
)
ASSET_CANDIDATE_READ_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAssetCandidateInventoryRead.ps1"
)
ASSET_CANDIDATE_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAssetCandidateInventoryInspect.ps1"
)
AUTHORITATIVE_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
)


def run_powershell_script(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def remove_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def make_project_inventory(project_inventory_rel: str) -> dict:
    result = run_powershell_script(
        PROJECT_INVENTORY_READ_SCRIPT,
        "-ProjectRoot",
        ".",
        "-OutputPath",
        project_inventory_rel,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_asset_candidate_inventory_read_creates_sandbox_local_inventory_with_evidence_links():
    suffix = uuid.uuid4().hex
    generated_dir_rel = f"scripts/generated/pytest-asset-candidates-{suffix}"
    generated_dir_abs = REPO_ROOT / generated_dir_rel
    generated_dir_abs.mkdir(parents=True, exist_ok=True)

    model_rel = f"{generated_dir_rel}/pytest-{suffix}.fbx"
    model_abs = REPO_ROOT / model_rel
    model_abs.write_text("sandbox model placeholder", encoding="utf-8")

    metadata_rel = f"scripts/pytest-{suffix}.manifest.json"
    metadata_abs = REPO_ROOT / metadata_rel
    metadata_abs.write_text("{\"kind\":\"metadata\"}", encoding="utf-8")

    receipt_id = f"pytest-receipt-{suffix}"
    receipt_path = REPO_ROOT / "examples" / "sandbox" / "receipts" / f"{receipt_id}.json"
    write_json(
        receipt_path,
        {
            "schema_version": "1.0.0",
            "receipt_id": receipt_id,
            "files_written": [model_rel],
            "notes": ["Evidence link test"],
        },
    )

    project_inventory_rel = f"examples/sandbox/project-inventory/pytest-project-inventory-{suffix}.json"
    project_inventory_abs = REPO_ROOT / project_inventory_rel
    project_inventory = make_project_inventory(project_inventory_rel)

    output_rel = f"examples/sandbox/asset-candidates/pytest-asset-candidate-inventory-{suffix}.json"
    output_abs = REPO_ROOT / output_rel

    result = run_powershell_script(
        ASSET_CANDIDATE_READ_SCRIPT,
        "-ProjectInventoryPath",
        project_inventory_rel,
        "-OutputPath",
        output_rel,
    )
    assert result.returncode == 0, result.stderr
    assert output_abs.exists(), "asset candidate inventory file was not written"

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0.0"
    assert payload["output_path"] == output_rel
    assert payload["sandbox_root"] == "examples/sandbox"
    assert payload["source_project_inventory_id"] == project_inventory["inventory_id"]
    assert isinstance(payload["source_asset_candidates"], list)
    assert isinstance(payload["linked_sandbox_evidence"], dict)
    assert isinstance(payload["generated_candidate_folders"], list)
    assert any(
        path == generated_dir_rel
        or generated_dir_rel.startswith(path + "/")
        or path.startswith(generated_dir_rel + "/")
        for path in payload["generated_candidate_folders"]
    )
    assert receipt_id in payload["linked_sandbox_evidence"]["receipt_ids"]

    for scan_root in payload["scanned_roots"]:
        lowered = scan_root.lower().replace("\\", "/")
        assert "/cache/" not in f"/{lowered}/"
        assert not lowered.startswith("cache/")

    model_candidate = next(
        c for c in payload["source_asset_candidates"] if c["relative_path"] == model_rel
    )
    metadata_candidate = next(
        c for c in payload["source_asset_candidates"] if c["relative_path"] == metadata_rel
    )

    assert model_candidate["category"] == "character_source"
    assert model_candidate["confidence"] == "high"
    assert len(model_candidate["sha256"]) == 64
    assert receipt_id in model_candidate["evidence_links"]["receipt_ids"]
    assert metadata_candidate["category"] == "metadata_source"
    assert len(metadata_candidate["sha256"]) == 64
    assert "product_resolution" in payload["explicit_non_admissions"]
    assert "asset_id_claims" in payload["explicit_non_admissions"]
    assert "spawning" in payload["explicit_non_admissions"]
    assert "publishing" in payload["explicit_non_admissions"]

    remove_if_exists(output_abs)
    remove_if_exists(project_inventory_abs)
    remove_if_exists(receipt_path)
    remove_if_exists(metadata_abs)
    remove_if_exists(generated_dir_abs)


def test_asset_candidate_inventory_blocks_traversal_and_outside_paths():
    suffix = uuid.uuid4().hex
    project_inventory_rel = f"examples/sandbox/project-inventory/pytest-project-inventory-{suffix}.json"
    project_inventory_abs = REPO_ROOT / project_inventory_rel
    make_project_inventory(project_inventory_rel)

    blocked_output = run_powershell_script(
        ASSET_CANDIDATE_READ_SCRIPT,
        "-ProjectInventoryPath",
        project_inventory_rel,
        "-OutputPath",
        "../outside/asset-candidate-inventory.json",
    )
    assert blocked_output.returncode != 0
    assert "blocked" in (blocked_output.stdout + blocked_output.stderr).lower() or "sandbox" in (
        blocked_output.stdout + blocked_output.stderr
    ).lower()

    blocked_inventory = run_powershell_script(
        ASSET_CANDIDATE_READ_SCRIPT,
        "-ProjectInventoryPath",
        "../outside/project-inventory.json",
    )
    assert blocked_inventory.returncode != 0
    assert "blocked" in (blocked_inventory.stdout + blocked_inventory.stderr).lower() or "sandbox" in (
        blocked_inventory.stdout + blocked_inventory.stderr
    ).lower()

    remove_if_exists(project_inventory_abs)


def test_asset_candidate_inventory_skips_cache_scan_roots():
    suffix = uuid.uuid4().hex
    cache_root_rel = f"cache/pytest-asset-candidates-{suffix}"
    cache_root_abs = REPO_ROOT / cache_root_rel
    cache_root_abs.mkdir(parents=True, exist_ok=True)
    cache_file_rel = f"{cache_root_rel}/cached-model-{suffix}.fbx"
    cache_file_abs = REPO_ROOT / cache_file_rel
    cache_file_abs.write_text("blocked cache file", encoding="utf-8")

    allowed_root_rel = f"scripts/generated/pytest-allowed-assets-{suffix}"
    allowed_root_abs = REPO_ROOT / allowed_root_rel
    allowed_root_abs.mkdir(parents=True, exist_ok=True)
    allowed_file_rel = f"{allowed_root_rel}/allowed-model-{suffix}.fbx"
    allowed_file_abs = REPO_ROOT / allowed_file_rel
    allowed_file_abs.write_text("allowed file", encoding="utf-8")

    project_inventory_rel = f"examples/sandbox/project-inventory/pytest-cache-project-inventory-{suffix}.json"
    project_inventory_abs = REPO_ROOT / project_inventory_rel
    write_json(
        project_inventory_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": f"project-inventory-cache-test-{suffix}",
            "project_root": ".",
            "known_asset_folders": [cache_root_rel, allowed_root_rel],
            "generated_asset_candidate_folders": [allowed_root_rel],
        },
    )

    output_rel = f"examples/sandbox/asset-candidates/pytest-cache-asset-candidate-inventory-{suffix}.json"
    output_abs = REPO_ROOT / output_rel

    result = run_powershell_script(
        ASSET_CANDIDATE_READ_SCRIPT,
        "-ProjectInventoryPath",
        project_inventory_rel,
        "-OutputPath",
        output_rel,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert any("cache is not an allowed scan root" in warning.lower() for warning in payload["warnings"])
    for scan_root in payload["scanned_roots"]:
        lowered = scan_root.lower().replace("\\", "/")
        assert "/cache/" not in f"/{lowered}/"
        assert not lowered.startswith("cache/")

    candidate_paths = [candidate["relative_path"] for candidate in payload["source_asset_candidates"]]
    assert allowed_file_rel in candidate_paths
    assert cache_file_rel not in candidate_paths

    remove_if_exists(output_abs)
    remove_if_exists(project_inventory_abs)
    remove_if_exists(cache_root_abs)
    remove_if_exists(allowed_root_abs)


def test_asset_candidate_inventory_inspect_is_read_only():
    suffix = uuid.uuid4().hex
    project_inventory_rel = f"examples/sandbox/project-inventory/pytest-project-inventory-{suffix}.json"
    project_inventory_abs = REPO_ROOT / project_inventory_rel
    project_inventory = make_project_inventory(project_inventory_rel)

    output_rel = f"examples/sandbox/asset-candidates/pytest-asset-candidate-inventory-{suffix}.json"
    output_abs = REPO_ROOT / output_rel
    read_result = run_powershell_script(
        ASSET_CANDIDATE_READ_SCRIPT,
        "-ProjectInventoryPath",
        project_inventory_rel,
        "-OutputPath",
        output_rel,
    )
    assert read_result.returncode == 0, read_result.stderr
    before = output_abs.read_bytes()
    payload = json.loads(read_result.stdout)

    list_result = run_powershell_script(ASSET_CANDIDATE_INSPECT_SCRIPT, "-List")
    assert list_result.returncode == 0, list_result.stderr
    list_payload = json.loads(list_result.stdout)
    assert list_payload["inventory_count"] >= 1

    by_id_result = run_powershell_script(
        ASSET_CANDIDATE_INSPECT_SCRIPT,
        "-InventoryId",
        payload["inventory_id"],
    )
    assert by_id_result.returncode == 0, by_id_result.stderr
    by_id_payload = json.loads(by_id_result.stdout)
    assert by_id_payload["inventory_id"] == payload["inventory_id"]
    assert "candidate_count" in by_id_payload

    by_path_result = run_powershell_script(
        ASSET_CANDIDATE_INSPECT_SCRIPT,
        "-InventoryPath",
        output_rel,
        "-ShowCandidates",
    )
    assert by_path_result.returncode == 0, by_path_result.stderr
    by_path_payload = json.loads(by_path_result.stdout)
    assert by_path_payload["inventory_id"] == payload["inventory_id"]
    assert isinstance(by_path_payload["source_asset_candidates"], list)

    after = output_abs.read_bytes()
    assert before == after, "inspect command mutated asset candidate inventory"
    assert payload["source_project_inventory_id"] == project_inventory["inventory_id"]

    remove_if_exists(output_abs)
    remove_if_exists(project_inventory_abs)


def test_authoritative_writer_absent_and_asset_candidate_commands_have_no_o3de_ap_editor_hooks():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        ASSET_CANDIDATE_READ_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + ASSET_CANDIDATE_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )
    for forbidden in [
        "o3de editor",
        "asset processor",
        "o3de.exe",
        "editor.exe",
        "assetprocessorbatch",
        "invoke-maxineauthoritativeresolverwrite.ps1",
    ]:
        assert forbidden not in combined


def test_asset_candidate_inventory_safety_verifier_passes():
    verifier = REPO_ROOT / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "safety verifier failed\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
