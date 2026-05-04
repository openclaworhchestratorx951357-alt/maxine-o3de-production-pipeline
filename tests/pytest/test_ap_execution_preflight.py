import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApEvidenceImport.ps1"
PREFLIGHT_BUILD_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApExecutionPreflightBuild.ps1"
PREFLIGHT_INSPECT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApExecutionPreflightInspect.ps1"
PREFLIGHT_BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApExecutionPreflightBundleExport.ps1"
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


def make_preflight_context() -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-preflight-{suffix}"
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

    project_rel = f"examples/sandbox/project-inventory/pytest-ap-preflight-project-{suffix}.json"
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
        f"examples/sandbox/asset-candidates/pytest-ap-preflight-asset-inventory-{suffix}.json"
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
        f"examples/sandbox/product-resolution-proposals/pytest-ap-preflight-proposal-{suffix}.json"
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

    ap_import_rel = f"examples/sandbox/ap-evidence-imports/pytest-ap-preflight-import-{suffix}.json"
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


def test_ap_execution_preflight_build_is_sandbox_local_and_non_executing():
    ctx = make_preflight_context()
    preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-preflight-{ctx['suffix']}.json"
    )
    preflight_abs = REPO_ROOT / preflight_rel

    model_hash_before = hashlib.sha256(ctx["model_abs"].read_bytes()).hexdigest()
    log_hash_before = hashlib.sha256(ctx["log_abs"].read_bytes()).hexdigest()

    result = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        preflight_rel,
    )
    assert result.returncode == 0, result.stderr
    assert preflight_abs.exists()

    payload = read_json(preflight_abs)
    assert payload["output_path"].startswith("examples/sandbox/ap-execution-preflights/")
    assert payload["required_manual_confirmation"] is True
    assert payload["local_only"] is True
    assert payload["execution_admitted"] is False
    assert payload["readiness_status"] in {
        "blocked_missing_evidence",
        "blocked_safety_boundary",
        "ready_for_future_execution_request",
        "rejected",
    }
    assert payload["proposed_ap_command_display"]
    assert "ap_batch_display_only" in payload["proposed_ap_command_display"]
    assert payload["proposed_ap_command_display"].find("|") == -1
    assert payload["proposed_ap_command_display"].find(";") == -1
    assert payload["proposed_ap_command_display"].find(">") == -1
    assert payload["proposed_ap_command_display"].find("<") == -1

    assert hashlib.sha256(ctx["model_abs"].read_bytes()).hexdigest() == model_hash_before
    assert hashlib.sha256(ctx["log_abs"].read_bytes()).hexdigest() == log_hash_before

    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_execution_preflight_blocks_traversal_and_outside_inputs(tmp_path: Path):
    ctx = make_preflight_context()

    outside_import = tmp_path / f"outside-import-{ctx['suffix']}.json"
    outside_import.write_text("{}", encoding="utf-8")

    blocked_outside = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        str(outside_import),
        "-ProposalPath",
        ctx["proposal_rel"],
    )
    assert blocked_outside.returncode != 0

    blocked_traversal_output = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-OutputPath",
        "../outside/preflight.json",
    )
    assert blocked_traversal_output.returncode != 0

    blocked_traversal_input = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        "../outside-import.json",
        "-ProposalPath",
        ctx["proposal_rel"],
    )
    assert blocked_traversal_input.returncode != 0

    cleanup_context(ctx)


def test_ap_execution_preflight_rejects_forbidden_readiness_statuses():
    ctx = make_preflight_context()

    blocked = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ReadinessStatus",
        "executed",
    )
    assert blocked.returncode != 0

    cleanup_context(ctx)


def test_ap_execution_preflight_inspect_is_read_only():
    ctx = make_preflight_context()
    preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-preflight-inspect-{ctx['suffix']}.json"
    )
    preflight_abs = REPO_ROOT / preflight_rel

    create = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        preflight_rel,
    )
    assert create.returncode == 0, create.stderr

    payload = read_json(preflight_abs)
    preflight_hash_before = hashlib.sha256(preflight_abs.read_bytes()).hexdigest()
    import_hash_before = hashlib.sha256(ctx["ap_import_abs"].read_bytes()).hexdigest()

    listed = run_powershell_script(PREFLIGHT_INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["preflight_count"] >= 1

    by_id = run_powershell_script(
        PREFLIGHT_INSPECT_SCRIPT,
        "-PreflightId",
        payload["preflight_id"],
        "-ShowBlockingReasons",
        "-ShowWarnings",
    )
    assert by_id.returncode == 0

    by_path = run_powershell_script(
        PREFLIGHT_INSPECT_SCRIPT,
        "-PreflightPath",
        preflight_rel,
    )
    assert by_path.returncode == 0

    assert hashlib.sha256(preflight_abs.read_bytes()).hexdigest() == preflight_hash_before
    assert hashlib.sha256(ctx["ap_import_abs"].read_bytes()).hexdigest() == import_hash_before

    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_ap_execution_preflight_bundle_is_json_only_and_sandbox_local():
    ctx = make_preflight_context()
    preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-preflight-bundle-{ctx['suffix']}.json"
    )
    preflight_abs = REPO_ROOT / preflight_rel
    bundle_rel = (
        "examples/sandbox/ap-execution-preflight-bundles/"
        f"pytest-ap-preflight-bundle-{ctx['suffix']}/bundle.manifest.json"
    )
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent

    create = run_powershell_script(
        PREFLIGHT_BUILD_SCRIPT,
        "-ApEvidenceImportPath",
        ctx["ap_import_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        preflight_rel,
    )
    assert create.returncode == 0, create.stderr

    source_hashes = {
        "preflight": hashlib.sha256(preflight_abs.read_bytes()).hexdigest(),
        "import": hashlib.sha256(ctx["ap_import_abs"].read_bytes()).hexdigest(),
        "proposal": hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest(),
        "project": hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest(),
    }

    bundle = run_powershell_script(
        PREFLIGHT_BUNDLE_SCRIPT,
        "-PreflightPath",
        preflight_rel,
        "-BundlePath",
        bundle_rel,
    )
    assert bundle.returncode == 0, bundle.stderr
    assert bundle_abs.exists()

    manifest = read_json(bundle_abs)
    assert manifest["bundle_path"].startswith("examples/sandbox/ap-execution-preflight-bundles/")
    for rel in manifest["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/ap-execution-preflight-bundles/")
        assert rel.endswith(".json")

    copied_names = {p.name.lower() for p in bundle_dir.rglob("*") if p.is_file()}
    assert ctx["model_abs"].name.lower() not in copied_names
    assert ctx["log_abs"].name.lower() not in copied_names

    assert hashlib.sha256(preflight_abs.read_bytes()).hexdigest() == source_hashes["preflight"]
    assert hashlib.sha256(ctx["ap_import_abs"].read_bytes()).hexdigest() == source_hashes["import"]
    assert hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest() == source_hashes["proposal"]
    assert hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest() == source_hashes["project"]

    blocked = run_powershell_script(
        PREFLIGHT_BUNDLE_SCRIPT,
        "-PreflightPath",
        preflight_rel,
        "-BundlePath",
        "../outside/bundle.manifest.json",
    )
    assert blocked.returncode != 0

    remove_if_exists(bundle_dir)
    remove_if_exists(preflight_abs)
    cleanup_context(ctx)


def test_global_ap_execution_preflight_safety_boundaries_remain_blocked():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        PREFLIGHT_BUILD_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + PREFLIGHT_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + PREFLIGHT_BUNDLE_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )

    for forbidden in [
        "o3de editor",
        "asset processor",
        "o3de.exe",
        "editor.exe",
        "invoke-maxineauthoritativeresolverwrite.ps1",
        "start-process",
        "invoke-expression",
    ]:
        assert forbidden not in combined



def test_capability_matrix_keeps_ap_execution_preflight_boundaries_blocked():
    matrix = read_json(REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json")
    caps = matrix["capabilities"]

    assert caps["ap_execution_preflight_build"] == "sandbox_only"
    assert caps["ap_execution_preflight_inspect"] == "read_only"
    assert caps["ap_execution_preflight_bundle_export"] == "sandbox_only"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["o3de_editor_execution"] == "blocked"
    assert caps["o3de_cli_execution"] == "blocked"
    assert caps["product_resolution"] == "blocked"
    assert caps["product_id_claims"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["source_uuid_claims"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"


def test_sandbox_writer_safety_verifier_passes_for_ap_execution_preflight_pack():
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
