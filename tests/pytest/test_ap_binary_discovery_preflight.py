import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_READ_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApBinaryDiscoveryRead.ps1"
DISCOVERY_INSPECT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApBinaryDiscoveryInspect.ps1"
BINARY_PREFLIGHT_BUILD_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApBinaryPreflightBuild.ps1"
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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def remove_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def make_binary_discovery_context() -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-binary-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    batch_rel = f"{generated_rel}/AssetProcessorBatch.exe"
    batch_abs = REPO_ROOT / batch_rel
    batch_abs.write_text("mock-batch", encoding="utf-8")

    unsupported_rel = f"{generated_rel}/tool-unknown.exe"
    unsupported_abs = REPO_ROOT / unsupported_rel
    unsupported_abs.write_text("mock-unknown", encoding="utf-8")

    source_preflight_id = f"ap-preflight-source-{suffix}"
    source_preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-binary-source-{suffix}.json"
    )
    source_preflight_abs = REPO_ROOT / source_preflight_rel
    write_json(
        source_preflight_abs,
        {
            "schema_version": "1.0.0",
            "preflight_id": source_preflight_id,
            "source_ap_evidence_import_id": f"ap-evidence-{suffix}",
            "source_proposal_id": f"proposal-{suffix}",
            "source_project_inventory_id": f"project-{suffix}",
            "sandbox_root": "examples/sandbox",
            "project_root": ".",
            "candidate_relative_path": "scripts/generated/example.fbx",
            "proposed_ap_command_display": "ap_batch_display_only --project-root . --candidate scripts/generated/example.fbx --mode preflight_display_only --no_execution",
            "proposed_working_directory": ".",
            "required_manual_confirmation": True,
            "local_only": True,
            "execution_admitted": False,
            "ready_for_future_execution_request": True,
            "readiness_status": "ready_for_future_execution_request",
            "required_next_evidence": ["ap_binary_discovery"],
            "blocking_reasons": [],
            "warnings": [],
            "safety_summary": "source preflight fixture",
            "explicit_non_admissions": [
                "authoritative_writes",
                "asset_processor_execution",
                "o3de_editor_execution",
                "o3de_cli_execution",
                "cache_read",
                "live_asset_database_read",
                "product_resolution",
                "product_id_claims",
                "asset_id_claims",
                "source_uuid_claims",
                "spawning",
                "publishing",
            ],
            "output_path": source_preflight_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "generated_rel": generated_rel,
        "batch_abs": batch_abs,
        "batch_rel": batch_rel,
        "unsupported_abs": unsupported_abs,
        "unsupported_rel": unsupported_rel,
        "source_preflight_abs": source_preflight_abs,
        "source_preflight_rel": source_preflight_rel,
    }


def cleanup_context(ctx: dict) -> None:
    for path in (
        ctx["source_preflight_abs"],
        ctx["batch_abs"],
        ctx["unsupported_abs"],
    ):
        remove_if_exists(path)
    remove_if_exists(ctx["generated_abs"])


def test_ap_binary_discovery_reads_explicit_candidate_metadata_only():
    ctx = make_binary_discovery_context()
    discovery_rel = f"examples/sandbox/ap-binary-discovery/pytest-ap-binary-discovery-{ctx['suffix']}.json"
    discovery_abs = REPO_ROOT / discovery_rel

    result = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        f"{ctx['batch_rel']},{ctx['unsupported_rel']}",
        "-OutputPath",
        discovery_rel,
    )
    assert result.returncode == 0, result.stderr
    assert discovery_abs.exists()

    payload = read_json(discovery_abs)
    assert payload["read_only"] is True
    assert payload["execution_admitted"] is False
    assert payload["cache_access_admitted"] is False
    assert payload["live_database_access_admitted"] is False
    assert payload["output_path"].startswith("examples/sandbox/ap-binary-discovery/")
    assert len(payload["candidate_paths"]) == 2
    assert len(payload["normalized_candidate_paths"]) == 2
    assert len(payload["existing_candidates"]) >= 1

    remove_if_exists(discovery_abs)
    cleanup_context(ctx)


def test_ap_binary_discovery_blocks_traversal_and_unsafe_paths():
    ctx = make_binary_discovery_context()

    blocked_traversal = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        "../outside/AssetProcessorBatch.exe",
    )
    assert blocked_traversal.returncode != 0

    blocked_unsafe = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        "AssetProcessorBatch.exe|Write-Host unsafe",
    )
    assert blocked_unsafe.returncode != 0

    blocked_output = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        ctx["batch_rel"],
        "-OutputPath",
        "../outside/discovery.json",
    )
    assert blocked_output.returncode != 0

    cleanup_context(ctx)


def test_ap_binary_discovery_inspect_is_read_only():
    ctx = make_binary_discovery_context()
    discovery_rel = f"examples/sandbox/ap-binary-discovery/pytest-ap-binary-inspect-{ctx['suffix']}.json"
    discovery_abs = REPO_ROOT / discovery_rel

    create = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        ctx["batch_rel"],
        "-OutputPath",
        discovery_rel,
    )
    assert create.returncode == 0, create.stderr

    payload = read_json(discovery_abs)
    before_hash = hashlib.sha256(discovery_abs.read_bytes()).hexdigest()

    listed = run_powershell_script(DISCOVERY_INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["discovery_count"] >= 1

    by_id = run_powershell_script(
        DISCOVERY_INSPECT_SCRIPT,
        "-DiscoveryId",
        payload["discovery_id"],
        "-ShowCandidates",
        "-ShowRejected",
    )
    assert by_id.returncode == 0

    by_path = run_powershell_script(
        DISCOVERY_INSPECT_SCRIPT,
        "-DiscoveryPath",
        discovery_rel,
    )
    assert by_path.returncode == 0

    assert hashlib.sha256(discovery_abs.read_bytes()).hexdigest() == before_hash

    remove_if_exists(discovery_abs)
    cleanup_context(ctx)


def test_ap_binary_preflight_builds_from_discovery_and_ap_execution_preflight():
    ctx = make_binary_discovery_context()
    discovery_rel = f"examples/sandbox/ap-binary-discovery/pytest-ap-binary-preflight-discovery-{ctx['suffix']}.json"
    discovery_abs = REPO_ROOT / discovery_rel
    preflight_rel = f"examples/sandbox/ap-binary-preflights/pytest-ap-binary-preflight-{ctx['suffix']}.json"
    preflight_abs = REPO_ROOT / preflight_rel

    create_discovery = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        ctx["batch_rel"],
        "-OutputPath",
        discovery_rel,
    )
    assert create_discovery.returncode == 0, create_discovery.stderr

    build = run_powershell_script(
        BINARY_PREFLIGHT_BUILD_SCRIPT,
        "-DiscoveryPath",
        discovery_rel,
        "-ApExecutionPreflightPath",
        ctx["source_preflight_rel"],
        "-OutputPath",
        preflight_rel,
    )
    assert build.returncode == 0, build.stderr
    assert preflight_abs.exists()

    payload = read_json(preflight_abs)
    assert payload["execution_admitted"] is False
    assert payload["required_manual_confirmation"] is True
    assert payload["local_only"] is True
    assert payload["binary_kind"] in {"AssetProcessorBatch", "AssetProcessor", "unknown"}
    assert payload["readiness_status"] in {
        "blocked_missing_binary",
        "blocked_unsupported_binary",
        "ready_for_future_real_ap_execution_request",
        "rejected",
    }

    remove_if_exists(preflight_abs)
    remove_if_exists(discovery_abs)
    cleanup_context(ctx)


def test_ap_binary_preflight_blocks_unsupported_binary_kind():
    ctx = make_binary_discovery_context()
    discovery_rel = f"examples/sandbox/ap-binary-discovery/pytest-ap-binary-unsupported-{ctx['suffix']}.json"
    preflight_rel = f"examples/sandbox/ap-binary-preflights/pytest-ap-binary-unsupported-{ctx['suffix']}.json"
    discovery_abs = REPO_ROOT / discovery_rel
    preflight_abs = REPO_ROOT / preflight_rel

    create_discovery = run_powershell_script(
        DISCOVERY_READ_SCRIPT,
        "-CandidatePaths",
        ctx["unsupported_rel"],
        "-OutputPath",
        discovery_rel,
    )
    assert create_discovery.returncode == 0, create_discovery.stderr

    build = run_powershell_script(
        BINARY_PREFLIGHT_BUILD_SCRIPT,
        "-DiscoveryPath",
        discovery_rel,
        "-ApExecutionPreflightPath",
        ctx["source_preflight_rel"],
        "-OutputPath",
        preflight_rel,
    )
    assert build.returncode == 0, build.stderr

    payload = read_json(preflight_abs)
    assert payload["readiness_status"] == "blocked_unsupported_binary"
    assert payload["execution_admitted"] is False

    remove_if_exists(preflight_abs)
    remove_if_exists(discovery_abs)
    cleanup_context(ctx)


def test_ap_binary_discovery_preflight_keeps_global_safety_boundaries():
    assert not AUTHORITATIVE_SCRIPT.exists()

    script_text = (
        DISCOVERY_READ_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + DISCOVERY_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + BINARY_PREFLIGHT_BUILD_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )

    for forbidden in (
        "start-process",
        "invoke-expression",
        "editor.exe",
        "o3de.exe",
    ):
        assert forbidden not in script_text

    matrix = read_json(REPO_ROOT / "examples/capabilities/maxine-capability-matrix.json")
    caps = matrix["capabilities"]
    assert caps["ap_binary_discovery_read"] == "read_only"
    assert caps["ap_binary_discovery_inspect"] == "read_only"
    assert caps["ap_binary_preflight_build"] == "sandbox_only"
    assert caps["real_asset_processor_execution"] == "blocked"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["product_resolution"] == "blocked"
    assert caps["product_id_claims"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["source_uuid_claims"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"
