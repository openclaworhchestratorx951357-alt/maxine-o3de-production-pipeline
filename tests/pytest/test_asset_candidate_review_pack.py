import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAssetCandidateReviewPacketBuild.ps1"
)
INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAssetCandidateReviewPacketInspect.ps1"
)
BUNDLE_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineAssetCandidateEvidenceBundleExport.ps1"
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_candidate_entry(candidate_id: str, rel_path: str, category: str, confidence: str) -> dict:
    full = REPO_ROOT / rel_path
    digest = hashlib.sha256(full.read_bytes()).hexdigest()
    return {
        "candidate_id": candidate_id,
        "relative_path": rel_path,
        "extension": full.suffix.lower(),
        "category": category,
        "size_bytes": full.stat().st_size,
        "sha256": digest,
        "last_write_time_utc": "2026-05-04T00:00:00Z",
        "evidence_links": {
            "receipt_ids": [f"receipt-{candidate_id}"],
            "review_packet_ids": [],
            "decision_ids": [],
            "workflow_run_ids": [],
            "evidence_bundle_ids": [],
        },
        "confidence": confidence,
        "notes": [f"candidate note for {candidate_id}"],
    }


def make_asset_candidate_inventory() -> dict:
    suffix = uuid.uuid4().hex
    generated_rel = f"scripts/generated/pytest-asset-candidate-review-pack-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    model_rel = f"{generated_rel}/model-{suffix}.fbx"
    texture_rel = f"{generated_rel}/albedo-{suffix}.png"
    meta_rel = f"{generated_rel}/model-{suffix}.manifest.json"

    (REPO_ROOT / model_rel).write_text("model-source", encoding="utf-8")
    (REPO_ROOT / texture_rel).write_text("texture-source", encoding="utf-8")
    (REPO_ROOT / meta_rel).write_text("{\"meta\":\"true\"}", encoding="utf-8")

    model_id = f"asset-candidate-model-{suffix}"
    texture_id = f"asset-candidate-texture-{suffix}"
    meta_id = f"asset-candidate-meta-{suffix}"

    inventory_rel = f"examples/sandbox/asset-candidates/pytest-asset-candidate-inventory-{suffix}.json"
    inventory_abs = REPO_ROOT / inventory_rel
    inventory_payload = {
        "schema_version": "1.0.0",
        "inventory_id": f"asset-inventory-{suffix}",
        "source_project_inventory_id": f"project-inventory-{suffix}",
        "project_root": ".",
        "sandbox_root": "examples/sandbox",
        "scanned_roots": [generated_rel],
        "generated_candidate_folders": [generated_rel],
        "source_asset_candidates": [
            build_candidate_entry(model_id, model_rel, "character_source", "high"),
            build_candidate_entry(texture_id, texture_rel, "texture_source", "medium"),
            build_candidate_entry(meta_id, meta_rel, "metadata_source", "medium"),
        ],
        "material_texture_candidates": [texture_id],
        "metadata_provenance_candidates": [meta_id],
        "linked_sandbox_evidence": {
            "receipt_ids": [f"receipt-{suffix}"],
            "review_packet_ids": [f"review-{suffix}"],
            "decision_ids": [f"decision-{suffix}"],
            "workflow_run_ids": [f"workflow-{suffix}"],
            "evidence_bundle_ids": [f"bundle-{suffix}"],
        },
        "warnings": [],
        "explicit_non_admissions": [
            "authoritative_writes",
            "product_resolution",
            "asset_id_claims",
            "spawning",
            "publishing",
            "o3de_editor_execution",
            "asset_processor_execution",
            "o3de_cli_execution",
            "cache_path_write",
            "engine_path_write",
            "production_path_write",
        ],
        "output_path": inventory_rel,
        "created_utc": "2026-05-04T00:00:00Z",
    }
    write_json(inventory_abs, inventory_payload)

    return {
        "suffix": suffix,
        "inventory_rel": inventory_rel,
        "inventory_abs": inventory_abs,
        "generated_abs": generated_abs,
        "model_rel": model_rel,
        "model_abs": REPO_ROOT / model_rel,
        "texture_rel": texture_rel,
        "texture_abs": REPO_ROOT / texture_rel,
        "meta_rel": meta_rel,
        "meta_abs": REPO_ROOT / meta_rel,
        "model_id": model_id,
        "texture_id": texture_id,
        "meta_id": meta_id,
    }


def test_review_packet_build_from_valid_asset_candidate_inventory():
    ctx = make_asset_candidate_inventory()
    packet_rel = (
        "examples/sandbox/asset-candidate-review-packets/"
        f"pytest-asset-candidate-review-packet-{ctx['suffix']}.json"
    )
    packet_abs = REPO_ROOT / packet_rel

    result = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "pending_review",
        "-RecommendedNextStep",
        "bundle_evidence",
        "-OperatorId",
        "pytest-operator",
    )
    assert result.returncode == 0, result.stderr
    assert packet_abs.exists()

    summary = json.loads(result.stdout)
    assert summary["review_packet_count"] == 1
    packet = read_json(packet_abs)
    inventory = read_json(ctx["inventory_abs"])
    source_candidate = next(
        c for c in inventory["source_asset_candidates"] if c["candidate_id"] == ctx["model_id"]
    )

    assert packet["schema_version"] == "1.0.0"
    assert packet["source_inventory_id"] == inventory["inventory_id"]
    assert packet["candidate_id"] == source_candidate["candidate_id"]
    assert packet["candidate_relative_path"] == source_candidate["relative_path"]
    assert packet["sha256"] == source_candidate["sha256"]
    assert packet["candidate_category"] == source_candidate["category"]
    assert packet["confidence"] == source_candidate["confidence"]
    assert packet["operator_decision_state"] == "pending_review"
    assert packet["recommended_next_step"] == "bundle_evidence"
    assert packet["output_path"].startswith("examples/sandbox/asset-candidate-review-packets/")

    remove_if_exists(packet_abs)
    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_review_packet_build_rejects_unknown_candidate_and_inventory_outside_sandbox():
    ctx = make_asset_candidate_inventory()

    unknown = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        "unknown-candidate",
    )
    assert unknown.returncode != 0
    assert "candidate_id" in (unknown.stdout + unknown.stderr).lower()

    outside_inventory = Path.cwd() / f"outside-inventory-{uuid.uuid4().hex}.json"
    write_json(
        outside_inventory,
        {
            "schema_version": "1.0.0",
            "inventory_id": "outside",
            "sandbox_root": "examples/sandbox",
            "source_asset_candidates": [],
        },
    )
    blocked = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        str(outside_inventory),
        "-CandidateId",
        "anything",
    )
    assert blocked.returncode != 0
    assert "sandbox root" in (blocked.stdout + blocked.stderr).lower() or "blocked" in (
        blocked.stdout + blocked.stderr
    ).lower() or "inventory root" in (
        blocked.stdout + blocked.stderr
    ).lower()

    remove_if_exists(outside_inventory)
    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_review_packet_build_rejects_forbidden_decisions_and_forbidden_next_steps():
    ctx = make_asset_candidate_inventory()

    forbidden_decision = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-OperatorDecisionState",
        "approve_product_resolution",
    )
    assert forbidden_decision.returncode != 0

    forbidden_step = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-RecommendedNextStep",
        "run_asset_processor",
    )
    assert forbidden_step.returncode != 0

    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_review_packet_build_writes_only_under_sandbox_review_packets_root():
    ctx = make_asset_candidate_inventory()

    blocked = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-OutputPath",
        "../outside/review-packet.json",
    )
    assert blocked.returncode != 0
    assert "sandbox root" in (blocked.stdout + blocked.stderr).lower() or "blocked" in (
        blocked.stdout + blocked.stderr
    ).lower()

    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_review_packet_inspect_is_read_only():
    ctx = make_asset_candidate_inventory()
    packet_rel = (
        "examples/sandbox/asset-candidate-review-packets/"
        f"pytest-asset-candidate-review-packet-{ctx['suffix']}.json"
    )
    packet_abs = REPO_ROOT / packet_rel

    build = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-OutputPath",
        packet_rel,
    )
    assert build.returncode == 0

    packet = read_json(packet_abs)
    inventory_before = ctx["inventory_abs"].read_bytes()
    packet_before = packet_abs.read_bytes()

    listed = run_powershell_script(INSPECT_SCRIPT, "-List")
    assert listed.returncode == 0
    listed_payload = json.loads(listed.stdout)
    assert listed_payload["review_packet_count"] >= 1

    by_id = run_powershell_script(
        INSPECT_SCRIPT,
        "-ReviewPacketId",
        packet["review_packet_id"],
    )
    assert by_id.returncode == 0
    by_id_payload = json.loads(by_id.stdout)
    assert by_id_payload["review_packet_id"] == packet["review_packet_id"]

    by_path = run_powershell_script(
        INSPECT_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-ShowEvidenceLinks",
    )
    assert by_path.returncode == 0
    by_path_payload = json.loads(by_path.stdout)
    assert by_path_payload["review_packet_id"] == packet["review_packet_id"]
    assert "evidence_links" in by_path_payload

    assert ctx["inventory_abs"].read_bytes() == inventory_before
    assert packet_abs.read_bytes() == packet_before

    remove_if_exists(packet_abs)
    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_candidate_evidence_bundle_export_is_sandbox_only_and_json_only_without_source_mutation():
    ctx = make_asset_candidate_inventory()
    packet_rel = (
        "examples/sandbox/asset-candidate-review-packets/"
        f"pytest-asset-candidate-review-packet-{ctx['suffix']}.json"
    )
    packet_abs = REPO_ROOT / packet_rel
    bundle_rel = (
        "examples/sandbox/asset-candidate-evidence-bundles/"
        f"pytest-asset-candidate-bundle-{ctx['suffix']}/bundle.manifest.json"
    )
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent

    build = run_powershell_script(
        BUILD_SCRIPT,
        "-InventoryPath",
        ctx["inventory_rel"],
        "-CandidateId",
        ctx["model_id"],
        "-OutputPath",
        packet_rel,
        "-RecommendedNextStep",
        "bundle_evidence",
    )
    assert build.returncode == 0, build.stderr
    packet_before = packet_abs.read_bytes()
    inventory_before = ctx["inventory_abs"].read_bytes()

    export = run_powershell_script(
        BUNDLE_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-BundlePath",
        bundle_rel,
    )
    assert export.returncode == 0, export.stderr
    assert bundle_abs.exists()

    manifest = read_json(bundle_abs)
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["bundle_path"].startswith("examples/sandbox/asset-candidate-evidence-bundles/")
    assert manifest["source_inventory_id"] == read_json(ctx["inventory_abs"])["inventory_id"]
    assert manifest["source_review_packet_id"] == read_json(packet_abs)["review_packet_id"]
    assert manifest["candidate_id"] == ctx["model_id"]

    assert manifest["included_artifacts"]
    assert manifest["copied_artifact_paths"]
    for rel in manifest["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/asset-candidate-evidence-bundles/")
        assert rel.endswith(".json")
        assert (REPO_ROOT / rel).exists()
        for forbidden_ext in [".fbx", ".glb", ".gltf", ".obj", ".blend", ".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bin", ".dll"]:
            assert not rel.lower().endswith(forbidden_ext)

    # Do not copy source assets/models/textures into the evidence bundle.
    copied_names = {p.name.lower() for p in bundle_dir.rglob("*") if p.is_file()}
    assert ctx["model_abs"].name.lower() not in copied_names
    assert ctx["texture_abs"].name.lower() not in copied_names

    assert ctx["inventory_abs"].read_bytes() == inventory_before
    assert packet_abs.read_bytes() == packet_before

    blocked_bundle = run_powershell_script(
        BUNDLE_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-BundlePath",
        "../outside/bundle.manifest.json",
    )
    assert blocked_bundle.returncode != 0

    remove_if_exists(bundle_dir)
    remove_if_exists(packet_abs)
    remove_if_exists(ctx["inventory_abs"])
    remove_if_exists(ctx["generated_abs"])


def test_authoritative_writer_absent_and_asset_candidate_review_pack_blocks_o3de_ap_editor_hooks():
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


def test_sandbox_writer_safety_verifier_passes_for_asset_candidate_review_pack():
    verifier = REPO_ROOT / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "sandbox writer safety verifier failed\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_capability_matrix_states_include_asset_candidate_review_pack():
    matrix_path = REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json"
    matrix = read_json(matrix_path)
    caps = matrix["capabilities"]

    assert caps["asset_candidate_review_packet_build"] == "sandbox_only"
    assert caps["asset_candidate_review_packet_inspect"] == "read_only"
    assert caps["asset_candidate_evidence_bundle_export"] == "sandbox_only"
    assert caps["authoritative_resolver_write"] == "forbidden"
    assert caps["product_resolution"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"
