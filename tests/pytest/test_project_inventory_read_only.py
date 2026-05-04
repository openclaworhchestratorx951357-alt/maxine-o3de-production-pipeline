import json
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_READ_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineProjectInventoryRead.ps1"
)
INVENTORY_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineProjectInventoryInspect.ps1"
)
AUTHORITATIVE_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
)
INVENTORY_DIR = REPO_ROOT / "examples" / "sandbox" / "project-inventory"


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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def test_project_inventory_read_writes_sandbox_output_with_required_fields(tmp_path: Path):
    output_rel = f"examples/sandbox/project-inventory/pytest-project-inventory-{uuid.uuid4().hex}.json"
    output_abs = REPO_ROOT / output_rel
    remove_if_exists(output_abs)

    result = run_powershell_script(
        INVENTORY_READ_SCRIPT,
        "-ProjectRoot",
        ".",
        "-OutputPath",
        output_rel,
    )
    assert result.returncode == 0, result.stderr
    assert output_abs.exists(), "inventory file was not written"

    payload = json.loads(result.stdout)
    assert payload["command_name"] == "Invoke-MaxineProjectInventoryRead.ps1"
    assert payload["inventory_path"] == output_rel
    assert payload["sandbox_root"] == "examples/sandbox"
    assert isinstance(payload["project_json_candidates"], list)
    assert isinstance(payload["gem_names"], list)
    assert isinstance(payload["known_asset_folders"], list)
    assert isinstance(payload["generated_asset_candidate_folders"], list)
    assert isinstance(payload["sandbox_evidence_folders"], list)
    assert isinstance(payload["o3de_project_path_metadata"], dict)
    assert isinstance(payload["configured_non_executed_path_hints"], dict)

    assert payload["safety"]["read_only_project_scan"] is True
    assert payload["safety"]["writes_limited_to_sandbox_inventory"] is True
    assert payload["safety"]["o3de_editor_execution_admitted"] is False
    assert payload["safety"]["asset_processor_execution_admitted"] is False
    assert payload["safety"]["product_resolution_admitted"] is False
    assert payload["safety"]["asset_id_claims_admitted"] is False
    assert payload["safety"]["spawning_admitted"] is False
    assert payload["safety"]["publishing_admitted"] is False

    remove_if_exists(output_abs)


def test_project_inventory_read_blocks_parent_traversal_output_path(tmp_path: Path):
    result = run_powershell_script(
        INVENTORY_READ_SCRIPT,
        "-ProjectRoot",
        ".",
        "-OutputPath",
        "../outside/project-inventory.json",
    )
    assert result.returncode != 0
    assert "blocked" in (result.stdout + result.stderr).lower() or "sandbox" in (
        result.stdout + result.stderr
    ).lower()


def test_project_inventory_inspect_list_and_id_are_read_only(tmp_path: Path):
    output_rel = f"examples/sandbox/project-inventory/pytest-project-inventory-{uuid.uuid4().hex}.json"
    output_abs = REPO_ROOT / output_rel
    remove_if_exists(output_abs)

    read_result = run_powershell_script(
        INVENTORY_READ_SCRIPT,
        "-ProjectRoot",
        ".",
        "-OutputPath",
        output_rel,
    )
    assert read_result.returncode == 0, read_result.stderr
    payload = json.loads(read_result.stdout)
    before = output_abs.read_bytes()

    inspect_list = run_powershell_script(INVENTORY_INSPECT_SCRIPT, "-List")
    assert inspect_list.returncode == 0, inspect_list.stderr
    list_payload = json.loads(inspect_list.stdout)
    assert list_payload["inventory_count"] >= 1

    inspect_id = run_powershell_script(
        INVENTORY_INSPECT_SCRIPT,
        "-InventoryId",
        payload["inventory_id"],
    )
    assert inspect_id.returncode == 0, inspect_id.stderr
    by_id_payload = json.loads(inspect_id.stdout)
    assert by_id_payload["inventory_id"] == payload["inventory_id"]

    inspect_path = run_powershell_script(
        INVENTORY_INSPECT_SCRIPT,
        "-InventoryPath",
        output_rel,
    )
    assert inspect_path.returncode == 0
    by_path_payload = json.loads(inspect_path.stdout)
    assert by_path_payload["inventory_path"] == output_rel

    after = output_abs.read_bytes()
    assert before == after, "inspect command mutated inventory record"

    remove_if_exists(output_abs)


def test_project_inventory_inspect_blocks_outside_inventory_root():
    result = run_powershell_script(
        INVENTORY_INSPECT_SCRIPT,
        "-InventoryPath",
        "../outside/inventory.json",
    )
    assert result.returncode != 0
    assert "blocked" in (result.stdout + result.stderr).lower() or "sandbox" in (
        result.stdout + result.stderr
    ).lower()


def test_authoritative_writer_absent_and_inventory_commands_have_no_o3de_ap_editor_execution_hooks():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        INVENTORY_READ_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + INVENTORY_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
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


def test_project_inventory_safety_verifier_passes():
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
