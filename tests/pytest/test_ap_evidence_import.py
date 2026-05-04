import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApEvidenceImport.ps1"
INSPECT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApEvidenceInspect.ps1"
BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApEvidenceBundleExport.ps1"
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


def make_ap_evidence_context() -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-evidence-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    model_rel = f"{generated_rel}/character-{suffix}.fbx"
    model_abs = REPO_ROOT / model_rel
    model_abs.write_text("binary-like-source", encoding="utf-8")

    log_rel = f"{generated_rel}/assetprocessor-export-{suffix}.log"
    log_abs = REPO_ROOT / log_rel
    log_abs.write_text(
        """Info: AP export imported only
Warning: material compile warning for scripts/generated/foo.material
Error: missing dependency for scripts/generated/foo.fbx
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
            "note": "copied snapshot metadata only",
            "product_hint": "Cache/project/model.azmodel",
            "source_hint": "scripts/generated/foo.fbx",
        },
    )

    project_id = f"project-inventory-{suffix}"
    asset_inventory_id = f"asset-inventory-{suffix}"
    proposal_id = f"product-resolution-proposal-{suffix}"

    project_rel = f"examples/sandbox/project-inventory/pytest-ap-evidence-project-{suffix}.json"
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
        f"examples/sandbox/asset-candidates/pytest-ap-evidence-asset-inventory-{suffix}.json"
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
        f"examples/sandbox/product-resolution-proposals/pytest-ap-evidence-proposal-{suffix}.json"
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

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "generated_rel": generated_rel,
        "model_abs": model_abs,
        "model_rel": model_rel,
        "log_abs": log_abs,
        "log_rel": log_rel,
        "snapshot_abs": snapshot_abs,
        "snapshot_rel": snapshot_rel,
        "project_id": project_id,
        "project_abs": project_abs,
        "project_rel": project_rel,
        "asset_inventory_id": asset_inventory_id,
        "asset_inventory_abs": asset_inventory_abs,
        "asset_inventory_rel": asset_inventory_rel,
        "proposal_id": proposal_id,
        "proposal_abs": proposal_abs,
        "proposal_rel": proposal_rel,
    }


def cleanup_context(ctx: dict) -> None:
    for path in (
        ctx["proposal_abs"],
        ctx["project_abs"],
        ctx["asset_inventory_abs"],
        ctx["log_abs"],
        ctx["snapshot_abs"],
        ctx["model_abs"],
    ):
        remove_if_exists(path)
    remove_if_exists(ctx["generated_abs"])


def test_ap_evidence_import_is_read_only_and_sandbox_local():
    ctx = make_ap_evidence_context()
    import_rel = f"examples/sandbox/ap-evidence-imports/pytest-ap-evidence-import-{ctx['suffix']}.json"
    import_abs = REPO_ROOT / import_rel

    result = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-EvidencePaths",
        f"{ctx['log_rel']},{ctx['snapshot_rel']}",
        "-OutputPath",
        import_rel,
    )
    assert result.returncode == 0, result.stderr
    assert import_abs.exists()

    payload = read_json(import_abs)
    assert payload["read_only"] is True
    assert payload["asset_processor_execution_admitted"] is False
    assert payload["o3de_execution_admitted"] is False
    assert payload["cache_access_admitted"] is False
    assert payload["live_database_access_admitted"] is False
    assert payload["product_ids_claimed"] is False
    assert payload["asset_ids_claimed"] is False
    assert payload["source_uuids_claimed"] is False
    assert payload["product_resolution_claimed"] is False
    assert payload["spawn_admitted"] is False
    assert payload["publish_admitted"] is False
    assert payload["output_path"].startswith("examples/sandbox/ap-evidence-imports/")
    assert payload["evidence_quality"] in {"none", "weak", "partial", "strong_snapshot_only"}
    assert payload["observed_product_like_mentions"]

    remove_if_exists(import_abs)
    cleanup_context(ctx)


def test_ap_evidence_import_blocks_outside_traversal_cache_sqlite_and_binary_inputs(tmp_path: Path):
    ctx = make_ap_evidence_context()

    outside_log = tmp_path / f"outside-{ctx['suffix']}.log"
    outside_log.write_text("Warning: outside", encoding="utf-8")

    blocked_outside = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        str(outside_log),
    )
    assert blocked_outside.returncode != 0

    blocked_traversal = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        "../outside.log",
    )
    assert blocked_traversal.returncode != 0

    cache_log_rel = f"cache/pytest-ap-evidence-{ctx['suffix']}.log"
    cache_log_abs = REPO_ROOT / cache_log_rel
    cache_log_abs.parent.mkdir(parents=True, exist_ok=True)
    cache_log_abs.write_text("cache evidence", encoding="utf-8")

    blocked_cache = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        cache_log_rel,
    )
    assert blocked_cache.returncode != 0

    sqlite_rel = f"scripts/generated/pytest-ap-evidence-{ctx['suffix']}-assetdb.sqlite"
    sqlite_abs = REPO_ROOT / sqlite_rel
    sqlite_abs.parent.mkdir(parents=True, exist_ok=True)
    sqlite_abs.write_text("sqlite", encoding="utf-8")

    blocked_sqlite = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        sqlite_rel,
    )
    assert blocked_sqlite.returncode != 0

    blocked_binary = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        ctx["model_rel"],
    )
    assert blocked_binary.returncode != 0

    remove_if_exists(cache_log_abs)
    remove_if_exists(sqlite_abs)
    cleanup_context(ctx)


def test_ap_evidence_inspect_is_read_only():
    ctx = make_ap_evidence_context()
    import_rel = f"examples/sandbox/ap-evidence-imports/pytest-ap-evidence-inspect-{ctx['suffix']}.json"
    import_abs = REPO_ROOT / import_rel

    create = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-EvidencePaths",
        f"{ctx['log_rel']},{ctx['snapshot_rel']}",
        "-OutputPath",
        import_rel,
    )
    assert create.returncode == 0, create.stderr

    payload = read_json(import_abs)
    import_hash_before = hashlib.sha256(import_abs.read_bytes()).hexdigest()
    log_hash_before = hashlib.sha256(ctx["log_abs"].read_bytes()).hexdigest()

    listed = run_powershell_script(INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["evidence_import_count"] >= 1

    by_id = run_powershell_script(
        INSPECT_SCRIPT,
        "-EvidenceImportId",
        payload["ap_evidence_import_id"],
        "-ShowWarnings",
        "-ShowErrors",
        "-ShowObservedMentions",
    )
    assert by_id.returncode == 0

    by_path = run_powershell_script(
        INSPECT_SCRIPT,
        "-EvidenceImportPath",
        import_rel,
    )
    assert by_path.returncode == 0

    assert hashlib.sha256(import_abs.read_bytes()).hexdigest() == import_hash_before
    assert hashlib.sha256(ctx["log_abs"].read_bytes()).hexdigest() == log_hash_before

    remove_if_exists(import_abs)
    cleanup_context(ctx)


def test_ap_evidence_bundle_export_is_sandbox_only_json_only_and_preserves_sources():
    ctx = make_ap_evidence_context()
    import_rel = f"examples/sandbox/ap-evidence-imports/pytest-ap-evidence-bundle-import-{ctx['suffix']}.json"
    import_abs = REPO_ROOT / import_rel
    bundle_rel = (
        "examples/sandbox/ap-evidence-bundles/"
        f"pytest-ap-evidence-bundle-{ctx['suffix']}/bundle.manifest.json"
    )
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent

    create = run_powershell_script(
        IMPORT_SCRIPT,
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-EvidencePaths",
        f"{ctx['log_rel']},{ctx['snapshot_rel']}",
        "-OutputPath",
        import_rel,
    )
    assert create.returncode == 0, create.stderr

    source_hashes = {
        "import": hashlib.sha256(import_abs.read_bytes()).hexdigest(),
        "proposal": hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest(),
        "project": hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest(),
        "asset_inventory": hashlib.sha256(ctx["asset_inventory_abs"].read_bytes()).hexdigest(),
    }

    bundle = run_powershell_script(
        BUNDLE_SCRIPT,
        "-EvidenceImportPath",
        import_rel,
        "-BundlePath",
        bundle_rel,
    )
    assert bundle.returncode == 0, bundle.stderr
    assert bundle_abs.exists()

    manifest = read_json(bundle_abs)
    assert manifest["bundle_path"].startswith("examples/sandbox/ap-evidence-bundles/")
    for rel in manifest["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/ap-evidence-bundles/")
        assert rel.endswith(".json")
        assert (REPO_ROOT / rel).exists()

    copied_names = {p.name.lower() for p in bundle_dir.rglob("*") if p.is_file()}
    assert ctx["model_abs"].name.lower() not in copied_names
    assert ctx["log_abs"].name.lower() not in copied_names

    assert hashlib.sha256(import_abs.read_bytes()).hexdigest() == source_hashes["import"]
    assert hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest() == source_hashes["proposal"]
    assert hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest() == source_hashes["project"]
    assert hashlib.sha256(ctx["asset_inventory_abs"].read_bytes()).hexdigest() == source_hashes["asset_inventory"]

    blocked = run_powershell_script(
        BUNDLE_SCRIPT,
        "-EvidenceImportPath",
        import_rel,
        "-BundlePath",
        "../outside/bundle.manifest.json",
    )
    assert blocked.returncode != 0

    remove_if_exists(bundle_dir)
    remove_if_exists(import_abs)
    cleanup_context(ctx)


def test_global_safety_boundaries_remain_blocked_for_ap_evidence_pack():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        IMPORT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + BUNDLE_SCRIPT.read_text(encoding="utf-8-sig").lower()
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


def test_capability_matrix_keeps_ap_evidence_boundaries_blocked():
    matrix = read_json(REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json")
    caps = matrix["capabilities"]

    assert caps["ap_evidence_import"] == "read_only"
    assert caps["ap_evidence_inspect"] == "read_only"
    assert caps["ap_evidence_bundle_export"] == "sandbox_only"
    assert caps["product_resolution"] == "blocked"
    assert caps["product_id_claims"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["source_uuid_claims"] == "blocked"
    assert caps["cache_read"] == "blocked"
    assert caps["live_asset_database_read"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"


def test_sandbox_writer_safety_verifier_passes_for_ap_evidence_pack():
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
