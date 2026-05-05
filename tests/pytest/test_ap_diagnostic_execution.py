import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApEvidenceImport.ps1"
PREFLIGHT_BUILD_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApExecutionPreflightBuild.ps1"
DIAG_EXEC_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApDiagnosticExecution.ps1"
DIAG_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApDiagnosticExecutionInspect.ps1"
)
DIAG_BUNDLE_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApDiagnosticExecutionBundleExport.ps1"
)
AUTHORITATIVE_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
)


ALLOWED_PRELIGHT_STATUSES = {
    "blocked_missing_evidence",
    "blocked_safety_boundary",
    "ready_for_future_execution_request",
    "rejected",
}


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


def make_preflight_context() -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-diag-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    model_rel = f"{generated_rel}/character-{suffix}.fbx"
    model_abs = REPO_ROOT / model_rel
    model_abs.write_text("binary-like-source", encoding="utf-8")

    log_rel = f"{generated_rel}/ap-export-{suffix}.log"
    log_abs = REPO_ROOT / log_rel
    log_abs.write_text(
        """Info: AP export imported only
Warning: pipeline warning mention
ProductCandidate: Cache/project/model.azmodel
SourcePath: scripts/generated/foo.fbx
""",
        encoding="utf-8",
    )

    snapshot_rel = f"{generated_rel}/ap-snapshot-{suffix}.json"
    snapshot_abs = REPO_ROOT / snapshot_rel
    write_json(
        snapshot_abs,
        {
            "snapshot_type": "ap_metadata",
            "product_hint": "Cache/project/model.azmodel",
            "source_hint": "scripts/generated/foo.fbx",
        },
    )

    project_id = f"project-inventory-{suffix}"
    asset_inventory_id = f"asset-inventory-{suffix}"
    proposal_id = f"product-resolution-proposal-{suffix}"

    project_rel = f"examples/sandbox/project-inventory/pytest-ap-diag-project-{suffix}.json"
    project_abs = REPO_ROOT / project_rel
    write_json(
        project_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": project_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "known_asset_folders": [generated_rel],
            "output_path": project_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    asset_inventory_rel = (
        f"examples/sandbox/asset-candidates/pytest-ap-diag-asset-inventory-{suffix}.json"
    )
    asset_inventory_abs = REPO_ROOT / asset_inventory_rel
    write_json(
        asset_inventory_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": asset_inventory_id,
            "source_project_inventory_id": project_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "scanned_roots": [generated_rel],
            "generated_candidate_folders": [generated_rel],
            "source_asset_candidates": [],
            "material_texture_candidates": [],
            "metadata_provenance_candidates": [],
            "linked_sandbox_evidence": {},
            "warnings": [],
            "explicit_non_admissions": [
                "authoritative_writes",
                "product_resolution",
                "asset_id_claims",
                "source_uuid_claims",
                "spawning",
                "publishing",
                "o3de_editor_execution",
                "asset_processor_execution",
                "cache_read",
            ],
            "output_path": asset_inventory_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    proposal_rel = (
        f"examples/sandbox/product-resolution-proposals/pytest-ap-diag-proposal-{suffix}.json"
    )
    proposal_abs = REPO_ROOT / proposal_rel
    write_json(
        proposal_abs,
        {
            "schema_version": "1.0.0",
            "proposal_id": proposal_id,
            "source_review_packet_id": f"review-packet-{suffix}",
            "source_inventory_id": asset_inventory_id,
            "source_project_inventory_id": project_id,
            "candidate_id": f"candidate-{suffix}",
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "candidate_relative_path": model_rel,
            "candidate_extension": ".fbx",
            "candidate_category": "character_source",
            "candidate_sha256": hashlib.sha256(model_abs.read_bytes()).hexdigest(),
            "proposal_status": "proposal_only",
            "expected_product_classes": ["model_product_candidate"],
            "likely_asset_pipeline_requirements": ["proposal_only"],
            "required_next_evidence": ["read_only_ap_evidence_import"],
            "blocking_reasons": [],
            "warnings": [],
            "proposal_only": True,
            "product_ids_claimed": False,
            "asset_ids_claimed": False,
            "source_uuids_claimed": False,
            "asset_processor_execution_admitted": False,
            "o3de_execution_admitted": False,
            "cache_access_admitted": False,
            "spawn_admitted": False,
            "publish_admitted": False,
            "safety_summary": "proposal only",
            "explicit_non_admissions": [
                "authoritative_writes",
                "product_resolution",
                "asset_id_claims",
                "source_uuid_claims",
                "spawning",
                "publishing",
                "o3de_editor_execution",
                "asset_processor_execution",
                "cache_read",
            ],
            "output_path": proposal_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    ap_import_rel = f"examples/sandbox/ap-evidence-imports/pytest-ap-diag-import-{suffix}.json"
    ap_import_abs = REPO_ROOT / ap_import_rel
    ap_import = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        proposal_rel,
        "-ProjectInventoryPath",
        project_rel,
        "-AssetCandidateInventoryPath",
        asset_inventory_rel,
        "-EvidencePaths",
        f"{log_rel},{snapshot_rel}",
        "-OutputPath",
        ap_import_rel,
    )
    assert ap_import.returncode == 0, ap_import.stderr

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "model_abs": model_abs,
        "model_rel": model_rel,
        "log_abs": log_abs,
        "log_rel": log_rel,
        "snapshot_abs": snapshot_abs,
        "snapshot_rel": snapshot_rel,
        "project_abs": project_abs,
        "project_rel": project_rel,
        "asset_inventory_abs": asset_inventory_abs,
        "asset_inventory_rel": asset_inventory_rel,
        "proposal_abs": proposal_abs,
        "proposal_rel": proposal_rel,
        "ap_import_abs": ap_import_abs,
        "ap_import_rel": ap_import_rel,
    }


def cleanup_context(ctx: dict) -> None:
    for path in (
        ctx["proposal_abs"],
        ctx["project_abs"],
        ctx["asset_inventory_abs"],
        ctx["ap_import_abs"],
        ctx["log_abs"],
        ctx["snapshot_abs"],
        ctx["model_abs"],
    ):
        remove_if_exists(path)
    remove_if_exists(ctx["generated_abs"])


def create_preflight(ctx: dict, readiness_status: str = "ready_for_future_execution_request") -> tuple[str, Path]:
    assert readiness_status in ALLOWED_PRELIGHT_STATUSES
    preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-diag-preflight-{ctx['suffix']}-{readiness_status}.json"
    )
    preflight_abs = REPO_ROOT / preflight_rel

    result = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-ReadinessStatus",
        readiness_status,
        "-OutputPath",
        preflight_rel,
    )
    assert result.returncode == 0, result.stderr
    assert preflight_abs.exists()
    return preflight_rel, preflight_abs


def run_diag(preflight_rel: str, suffix: str, *args: str) -> tuple[subprocess.CompletedProcess[str], str, Path]:
    diag_rel = f"examples/sandbox/ap-diagnostic-executions/pytest-ap-diag-exec-{suffix}-{uuid.uuid4().hex}.json"
    diag_abs = REPO_ROOT / diag_rel
    result = run_powershell_script(
        DIAG_EXEC_SCRIPT,
        "-PreflightPath",
        preflight_rel,
        "-OutputPath",
        diag_rel,
        *args,
    )
    return result, diag_rel, diag_abs


def test_ap_diag_execution_blocks_without_approval_flag():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    result, _, diag_abs = run_diag(preflight_rel, ctx["suffix"], "-UseMockDiagnosticCommand")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "blocked"
    assert payload["command_executed"] is False
    assert "without approval flag" in payload["blocked_reason"]

    remove_if_exists(diag_abs)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_execution_blocks_unready_preflight():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx, readiness_status="blocked_missing_evidence")

    result, _, diag_abs = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "blocked"
    assert payload["command_executed"] is False
    assert "readiness_status" in payload["blocked_reason"]

    remove_if_exists(diag_abs)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_execution_blocks_when_preflight_admission_or_local_only_is_invalid():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    preflight = read_json(preflight_abs)
    preflight["execution_admitted"] = True
    write_json(preflight_abs, preflight)

    blocked_admitted, _, diag_abs_1 = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert blocked_admitted.returncode == 0, blocked_admitted.stderr
    payload_1 = json.loads(blocked_admitted.stdout)
    assert payload_1["execution_status"] == "blocked"
    assert "execution_admitted=true" in payload_1["blocked_reason"]

    preflight["execution_admitted"] = False
    preflight["local_only"] = False
    write_json(preflight_abs, preflight)

    blocked_local_only, _, diag_abs_2 = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert blocked_local_only.returncode == 0, blocked_local_only.stderr
    payload_2 = json.loads(blocked_local_only.stdout)
    assert payload_2["execution_status"] == "blocked"
    assert "local_only must be true" in payload_2["blocked_reason"]

    remove_if_exists(diag_abs_1)
    remove_if_exists(diag_abs_2)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_execution_blocks_arbitrary_or_unsafe_command_display():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    preflight = read_json(preflight_abs)
    preflight["proposed_ap_command_display"] = "user supplied command text"
    write_json(preflight_abs, preflight)

    blocked_arbitrary, _, diag_abs_1 = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert blocked_arbitrary.returncode == 0, blocked_arbitrary.stderr
    payload_1 = json.loads(blocked_arbitrary.stdout)
    assert payload_1["execution_status"] == "blocked"
    assert "arbitrary user text" in payload_1["blocked_reason"]

    preflight["proposed_ap_command_display"] = (
        "ap_batch_display_only --project-root . --candidate scripts/generated/a.fbx --mode preflight_display_only --no_execution | malicious"
    )
    write_json(preflight_abs, preflight)

    blocked_unsafe, _, diag_abs_2 = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert blocked_unsafe.returncode == 0, blocked_unsafe.stderr
    payload_2 = json.loads(blocked_unsafe.stdout)
    assert payload_2["execution_status"] == "blocked"
    assert "shell operators" in payload_2["blocked_reason"]

    remove_if_exists(diag_abs_1)
    remove_if_exists(diag_abs_2)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_execution_succeeds_with_mock_and_records_hashes_and_flags():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    result, _, diag_abs = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "succeeded"
    assert payload["command_executed"] is True
    assert payload["command_allowlisted"] is True
    assert payload["execution_mode"] == "DiagnosticOnly"
    assert payload["local_only"] is True
    assert payload["output_path"].startswith("examples/sandbox/ap-diagnostic-executions/")
    assert payload["stdout_path"].startswith("examples/sandbox/ap-diagnostic-executions/")
    assert payload["stderr_path"].startswith("examples/sandbox/ap-diagnostic-executions/")
    assert payload["stdout_sha256"]
    assert payload["stderr_sha256"]
    assert payload["exit_code"] == 0

    stdout_abs = REPO_ROOT / payload["stdout_path"]
    stderr_abs = REPO_ROOT / payload["stderr_path"]
    assert stdout_abs.exists()
    assert stderr_abs.exists()
    assert hashlib.sha256(stdout_abs.read_bytes()).hexdigest().upper() == payload["stdout_sha256"]
    assert hashlib.sha256(stderr_abs.read_bytes()).hexdigest().upper() == payload["stderr_sha256"]

    assert payload["product_ids_claimed"] is False
    assert payload["asset_ids_claimed"] is False
    assert payload["source_uuids_claimed"] is False
    assert payload["product_resolution_claimed"] is False
    assert payload["cache_access_admitted"] is False
    assert payload["live_database_access_admitted"] is False
    assert payload["spawn_admitted"] is False
    assert payload["publish_admitted"] is False

    remove_if_exists(stdout_abs)
    remove_if_exists(stderr_abs)
    remove_if_exists(diag_abs)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_execution_can_record_timed_out_status_in_simulation_mode():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    result, _, diag_abs = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
        "-SimulateTimeout",
        "-TimeoutSeconds",
        "2",
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "timed_out"
    assert payload["command_executed"] is True
    assert payload["exit_code"] == 124

    stdout_abs = REPO_ROOT / payload["stdout_path"]
    stderr_abs = REPO_ROOT / payload["stderr_path"]
    assert stdout_abs.exists()
    assert stderr_abs.exists()

    remove_if_exists(stdout_abs)
    remove_if_exists(stderr_abs)
    remove_if_exists(diag_abs)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_inspect_is_read_only_and_bundle_is_json_stdout_stderr_text_only():
    ctx = make_preflight_context()
    preflight_rel, preflight_abs = create_preflight(ctx)

    create, _, diag_abs = run_diag(
        preflight_rel,
        ctx["suffix"],
        "-ApproveLocalDiagnosticExecution",
        "-UseMockDiagnosticCommand",
    )
    assert create.returncode == 0, create.stderr
    diag = json.loads(create.stdout)

    diag_hash_before = hashlib.sha256(diag_abs.read_bytes()).hexdigest()
    stdout_abs = REPO_ROOT / diag["stdout_path"]
    stderr_abs = REPO_ROOT / diag["stderr_path"]
    stdout_hash_before = hashlib.sha256(stdout_abs.read_bytes()).hexdigest()
    stderr_hash_before = hashlib.sha256(stderr_abs.read_bytes()).hexdigest()

    listed = run_powershell_script(DIAG_INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["diagnostic_execution_count"] >= 1

    by_id = run_powershell_script(
        DIAG_INSPECT_SCRIPT,
        "-DiagnosticExecutionId",
        diag["diagnostic_execution_id"],
        "-ShowOutputRefs",
        "-ShowBlockedReason",
    )
    assert by_id.returncode == 0

    assert hashlib.sha256(diag_abs.read_bytes()).hexdigest() == diag_hash_before
    assert hashlib.sha256(stdout_abs.read_bytes()).hexdigest() == stdout_hash_before
    assert hashlib.sha256(stderr_abs.read_bytes()).hexdigest() == stderr_hash_before

    bundle_rel = (
        f"examples/sandbox/ap-diagnostic-execution-bundles/pytest-ap-diag-{ctx['suffix']}/bundle.manifest.json"
    )
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent

    bundle = run_powershell_script(
        DIAG_BUNDLE_SCRIPT,
        "-DiagnosticExecutionPath",
        diag["output_path"],
        "-BundlePath",
        bundle_rel,
    )
    assert bundle.returncode == 0, bundle.stderr
    manifest = json.loads(bundle.stdout)

    assert bundle_abs.exists()
    assert manifest["bundle_path"].startswith("examples/sandbox/ap-diagnostic-execution-bundles/")
    for rel in manifest["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/ap-diagnostic-execution-bundles/")
        lower = rel.lower()
        assert lower.endswith(".json") or lower.endswith(".txt")

    names = {p.name for p in bundle_dir.rglob("*") if p.is_file()}
    assert Path(ctx["model_rel"]).name not in names
    assert Path(ctx["log_rel"]).name not in names

    blocked_bundle = run_powershell_script(
        DIAG_BUNDLE_SCRIPT,
        "-DiagnosticExecutionPath",
        diag["output_path"],
        "-BundlePath",
        "../outside/bundle.manifest.json",
    )
    assert blocked_bundle.returncode != 0

    remove_if_exists(bundle_dir)
    remove_if_exists(stdout_abs)
    remove_if_exists(stderr_abs)
    remove_if_exists(diag_abs)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_diag_global_safety_boundaries_remain_blocked():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        DIAG_EXEC_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + DIAG_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + DIAG_BUNDLE_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )

    for token in (
        "assetprocessor.exe",
        "assetprocessorbatch.exe",
        "editor.exe",
        "o3de.exe",
        "invoke-maxineauthoritativeresolverwrite.ps1",
        "invoke-expression",
        "start-process",
    ):
        assert token not in combined

    matrix = read_json(REPO_ROOT / "examples/capabilities/maxine-capability-matrix.json")
    caps = matrix["capabilities"]
    assert caps["ap_diagnostic_execution"] == "sandbox_only"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["o3de_editor_execution"] == "blocked"
    assert caps["o3de_cli_execution"] == "blocked"
    assert caps["product_resolution"] == "blocked"
    assert caps["product_id_claims"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["source_uuid_claims"] == "blocked"
    assert caps["cache_read"] == "blocked"
    assert caps["live_asset_database_read"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"
