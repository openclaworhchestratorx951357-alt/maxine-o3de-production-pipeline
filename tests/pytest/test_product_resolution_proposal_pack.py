import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineProductResolutionProposalBuild.ps1"
)
INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineProductResolutionProposalInspect.ps1"
)
BUNDLE_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineProductResolutionProposalBundleExport.ps1"
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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def remove_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def make_review_context() -> dict:
    suffix = uuid.uuid4().hex
    generated_rel = f"scripts/generated/pytest-product-proposal-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    model_rel = f"{generated_rel}/character-{suffix}.fbx"
    model_abs = REPO_ROOT / model_rel
    model_abs.write_text("proposal-candidate-source", encoding="utf-8")
    model_sha = hashlib.sha256(model_abs.read_bytes()).hexdigest()

    project_id = f"project-inventory-{suffix}"
    asset_inventory_id = f"asset-inventory-{suffix}"
    review_packet_id = f"asset-candidate-review-{suffix}"
    candidate_id = f"asset-candidate-{suffix}"

    project_rel = f"examples/sandbox/project-inventory/pytest-product-proposal-project-{suffix}.json"
    project_abs = REPO_ROOT / project_rel
    write_json(
        project_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": project_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "project_json_candidates": ["project.json"],
            "known_asset_folders": [generated_rel],
            "generated_asset_candidate_folders": [generated_rel],
            "sandbox_evidence_folders": [
                "examples/sandbox/receipts",
                "examples/sandbox/review-packets",
                "examples/sandbox/review-decisions",
                "examples/sandbox/workflow-runs",
            ],
            "o3de_project_path_metadata": {"project_name_hint": "MaxineShow"},
            "configured_non_executed_path_hints": {
                "o3de_editor_path_hint": "C:/O3DE/Editor.exe",
                "asset_processor_path_hint": "C:/O3DE/AssetProcessorBatch.exe",
            },
            "output_path": project_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    asset_inv_rel = f"examples/sandbox/asset-candidates/pytest-product-proposal-asset-inventory-{suffix}.json"
    asset_inv_abs = REPO_ROOT / asset_inv_rel
    write_json(
        asset_inv_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": asset_inventory_id,
            "source_project_inventory_id": project_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "scanned_roots": [generated_rel],
            "generated_candidate_folders": [generated_rel],
            "source_asset_candidates": [
                {
                    "candidate_id": candidate_id,
                    "relative_path": model_rel,
                    "extension": ".fbx",
                    "category": "character_source",
                    "size_bytes": model_abs.stat().st_size,
                    "sha256": model_sha,
                    "last_write_time_utc": "2026-05-04T00:00:00Z",
                    "evidence_links": {
                        "receipt_ids": [f"receipt-{suffix}"],
                        "review_packet_ids": [],
                        "decision_ids": [],
                        "workflow_run_ids": [],
                        "evidence_bundle_ids": [],
                    },
                    "confidence": "high",
                    "notes": ["candidate source test fixture"],
                }
            ],
            "material_texture_candidates": [],
            "metadata_provenance_candidates": [],
            "linked_sandbox_evidence": {
                "receipt_ids": [f"receipt-{suffix}"],
                "review_packet_ids": [review_packet_id],
                "decision_ids": [],
                "workflow_run_ids": [f"workflow-{suffix}"],
                "evidence_bundle_ids": [],
            },
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
            "output_path": asset_inv_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    review_rel = f"examples/sandbox/asset-candidate-review-packets/pytest-product-proposal-review-{suffix}.json"
    review_abs = REPO_ROOT / review_rel
    write_json(
        review_abs,
        {
            "schema_version": "1.0.0",
            "review_packet_id": review_packet_id,
            "source_inventory_id": asset_inventory_id,
            "candidate_id": candidate_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "candidate_relative_path": model_rel,
            "candidate_extension": ".fbx",
            "candidate_category": "character_source",
            "size_bytes": model_abs.stat().st_size,
            "sha256": model_sha,
            "last_write_time_utc": "2026-05-04T00:00:00Z",
            "confidence": "high",
            "evidence_links": {
                "receipt_ids": [f"receipt-{suffix}"],
                "review_packet_ids": [],
                "decision_ids": [],
                "workflow_run_ids": [],
                "evidence_bundle_ids": [],
            },
            "provenance_links": [],
            "material_texture_links": [],
            "warnings": [],
            "safety_summary": "sandbox-only review packet",
            "recommended_next_step": "bundle_evidence",
            "operator_decision_state": "pending_review",
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
            "output_path": review_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "model_abs": model_abs,
        "model_rel": model_rel,
        "project_abs": project_abs,
        "project_rel": project_rel,
        "project_id": project_id,
        "asset_inventory_abs": asset_inv_abs,
        "asset_inventory_rel": asset_inv_rel,
        "asset_inventory_id": asset_inventory_id,
        "review_abs": review_abs,
        "review_rel": review_rel,
        "review_id": review_packet_id,
        "candidate_id": candidate_id,
        "model_sha": model_sha,
    }


def test_product_resolution_proposal_build_is_sandbox_only_and_proposal_only():
    ctx = make_review_context()
    proposal_rel = (
        "examples/sandbox/product-resolution-proposals/"
        f"pytest-product-proposal-{ctx['suffix']}.json"
    )
    proposal_abs = REPO_ROOT / proposal_rel

    result = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        proposal_rel,
        "-OperatorId",
        "pytest-operator",
    )
    assert result.returncode == 0, result.stderr
    assert proposal_abs.exists()
    proposal = read_json(proposal_abs)

    assert proposal["proposal_only"] is True
    assert proposal["product_ids_claimed"] is False
    assert proposal["asset_ids_claimed"] is False
    assert proposal["source_uuids_claimed"] is False
    assert proposal["asset_processor_execution_admitted"] is False
    assert proposal["o3de_execution_admitted"] is False
    assert proposal["cache_access_admitted"] is False
    assert proposal["spawn_admitted"] is False
    assert proposal["publish_admitted"] is False
    assert proposal["output_path"].startswith("examples/sandbox/product-resolution-proposals/")
    assert proposal["candidate_sha256"] == ctx["model_sha"]
    assert "model_product_candidate" in proposal["expected_product_classes"]
    assert "actor_product_candidate" in proposal["expected_product_classes"]
    assert proposal["proposal_status"] in {
        "proposal_only",
        "blocked_missing_evidence",
        "ready_for_read_only_ap_evidence_import",
        "rejected",
    }
    for forbidden_key in [
        "resolved_product_id",
        "resolved_asset_id",
        "source_uuid",
        "asset_processor_executed",
        "cache_verified",
        "spawned_entity",
        "published_asset",
    ]:
        assert forbidden_key not in proposal

    remove_if_exists(proposal_abs)
    remove_if_exists(ctx["review_abs"])
    remove_if_exists(ctx["asset_inventory_abs"])
    remove_if_exists(ctx["project_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_product_resolution_proposal_build_blocks_outside_review_packet_and_output_paths(tmp_path: Path):
    ctx = make_review_context()
    outside_review = tmp_path / "outside-review.json"
    write_json(
        outside_review,
        {
            "review_packet_id": "outside",
            "source_inventory_id": ctx["asset_inventory_id"],
            "candidate_id": ctx["candidate_id"],
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "candidate_relative_path": ctx["model_rel"],
            "candidate_extension": ".fbx",
            "candidate_category": "character_source",
            "sha256": ctx["model_sha"],
        },
    )

    blocked_review = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        str(outside_review),
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
    )
    assert blocked_review.returncode != 0

    blocked_output = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        "../outside/proposal.json",
    )
    assert blocked_output.returncode != 0

    remove_if_exists(outside_review)
    remove_if_exists(ctx["review_abs"])
    remove_if_exists(ctx["asset_inventory_abs"])
    remove_if_exists(ctx["project_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_product_resolution_proposal_build_rejects_forbidden_proposal_statuses():
    ctx = make_review_context()
    bad = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-ProposalStatus",
        "resolved",
    )
    assert bad.returncode != 0
    assert "forbidden" in (bad.stdout + bad.stderr).lower()

    remove_if_exists(ctx["review_abs"])
    remove_if_exists(ctx["asset_inventory_abs"])
    remove_if_exists(ctx["project_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_product_resolution_proposal_inspect_is_read_only():
    ctx = make_review_context()
    proposal_rel = (
        "examples/sandbox/product-resolution-proposals/"
        f"pytest-product-proposal-inspect-{ctx['suffix']}.json"
    )
    proposal_abs = REPO_ROOT / proposal_rel

    build = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        proposal_rel,
    )
    assert build.returncode == 0
    proposal = read_json(proposal_abs)

    review_before = ctx["review_abs"].read_bytes()
    proposal_before = proposal_abs.read_bytes()

    listed = run_powershell_script(INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["proposal_count"] >= 1

    by_id = run_powershell_script(
        INSPECT_SCRIPT,
        "-ProposalId",
        proposal["proposal_id"],
    )
    assert by_id.returncode == 0

    by_path = run_powershell_script(
        INSPECT_SCRIPT,
        "-ProposalPath",
        proposal_rel,
        "-ShowRequirements",
        "-ShowBlockingReasons",
    )
    assert by_path.returncode == 0
    assert json.loads(by_path.stdout)["proposal_id"] == proposal["proposal_id"]

    assert review_before == ctx["review_abs"].read_bytes()
    assert proposal_before == proposal_abs.read_bytes()

    remove_if_exists(proposal_abs)
    remove_if_exists(ctx["review_abs"])
    remove_if_exists(ctx["asset_inventory_abs"])
    remove_if_exists(ctx["project_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_product_resolution_proposal_bundle_export_is_sandbox_only_json_only_and_preserves_sources():
    ctx = make_review_context()
    proposal_rel = (
        "examples/sandbox/product-resolution-proposals/"
        f"pytest-product-proposal-bundle-{ctx['suffix']}.json"
    )
    proposal_abs = REPO_ROOT / proposal_rel
    bundle_rel = (
        "examples/sandbox/product-resolution-proposal-bundles/"
        f"pytest-product-proposal-bundle-{ctx['suffix']}/bundle.manifest.json"
    )
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent

    build = run_powershell_script(
        BUILD_SCRIPT,
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-AssetCandidateInventoryPath",
        ctx["asset_inventory_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
        "-OutputPath",
        proposal_rel,
    )
    assert build.returncode == 0, build.stderr

    source_hashes = {
        "review": hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest(),
        "proposal": hashlib.sha256(proposal_abs.read_bytes()).hexdigest(),
        "asset_inventory": hashlib.sha256(ctx["asset_inventory_abs"].read_bytes()).hexdigest(),
        "project_inventory": hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest(),
    }

    export = run_powershell_script(
        BUNDLE_SCRIPT,
        "-ProposalPath",
        proposal_rel,
        "-BundlePath",
        bundle_rel,
    )
    assert export.returncode == 0, export.stderr
    assert bundle_abs.exists()
    manifest = read_json(bundle_abs)

    assert manifest["bundle_path"].startswith("examples/sandbox/product-resolution-proposal-bundles/")
    assert manifest["source_proposal_id"] == read_json(proposal_abs)["proposal_id"]
    assert manifest["source_review_packet_id"] == read_json(ctx["review_abs"])["review_packet_id"]
    assert manifest["source_inventory_id"] == ctx["asset_inventory_id"]
    assert manifest["source_project_inventory_id"] == ctx["project_id"]
    assert manifest["candidate_id"] == ctx["candidate_id"]
    assert manifest["included_artifacts"]
    assert manifest["copied_artifact_paths"]
    for rel in manifest["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/product-resolution-proposal-bundles/")
        assert rel.endswith(".json")
        assert (REPO_ROOT / rel).exists()

    copied_names = {p.name.lower() for p in bundle_dir.rglob("*") if p.is_file()}
    assert ctx["model_abs"].name.lower() not in copied_names

    assert hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest() == source_hashes["review"]
    assert hashlib.sha256(proposal_abs.read_bytes()).hexdigest() == source_hashes["proposal"]
    assert hashlib.sha256(ctx["asset_inventory_abs"].read_bytes()).hexdigest() == source_hashes["asset_inventory"]
    assert hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest() == source_hashes["project_inventory"]

    blocked = run_powershell_script(
        BUNDLE_SCRIPT,
        "-ProposalPath",
        proposal_rel,
        "-BundlePath",
        "../outside/bundle.manifest.json",
    )
    assert blocked.returncode != 0

    remove_if_exists(bundle_dir)
    remove_if_exists(proposal_abs)
    remove_if_exists(ctx["review_abs"])
    remove_if_exists(ctx["asset_inventory_abs"])
    remove_if_exists(ctx["project_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_global_safety_boundaries_remain_blocked_for_proposal_pack():
    assert not AUTHORITATIVE_SCRIPT.exists()
    combined = (
        BUILD_SCRIPT.read_text(encoding="utf-8-sig").lower()
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


def test_capability_matrix_keeps_product_resolution_boundaries_blocked():
    matrix = read_json(REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json")
    caps = matrix["capabilities"]
    assert caps["product_resolution_proposal_build"] == "sandbox_only"
    assert caps["product_resolution_proposal_inspect"] == "read_only"
    assert caps["product_resolution_proposal_bundle_export"] == "sandbox_only"
    assert caps["product_resolution"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["source_uuid_claims"] == "blocked"
    assert caps["cache_read"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"


def test_sandbox_writer_safety_verifier_passes_for_proposal_pack():
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
