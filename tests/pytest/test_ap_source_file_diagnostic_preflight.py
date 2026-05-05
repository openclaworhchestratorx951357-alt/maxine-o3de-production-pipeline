import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_BUILD_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineApSourceFileDiagnosticPreflightBuild.ps1"
)
PREFLIGHT_INSPECT_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineApSourceFileDiagnosticPreflightInspect.ps1"
)
PREFLIGHT_BUNDLE_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineApSourceFileDiagnosticPreflightBundleExport.ps1"
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


def mutate_json(path: Path, updates: dict) -> None:
    payload = read_json(path)
    payload.update(updates)
    write_json(path, payload)


def make_source_file_preflight_context(include_real_diagnostic: bool = True) -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-source-file-preflight-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    source_rel = f"{generated_rel}/candidate-{suffix}.fbx"
    source_abs = REPO_ROOT / source_rel
    source_abs.write_text("source-file-fixture", encoding="utf-8")
    source_hash = hashlib.sha256(source_abs.read_bytes()).hexdigest()

    binary_rel = f"{generated_rel}/AssetProcessorBatch.exe"
    binary_abs = REPO_ROOT / binary_rel
    binary_abs.write_text("fake-ap-binary", encoding="utf-8")

    review_packet_id = f"asset-candidate-review-packet-{suffix}"
    proposal_id = f"product-resolution-proposal-{suffix}"
    preflight_id = f"ap-binary-preflight-{suffix}"
    project_id = f"project-inventory-{suffix}"
    real_diag_id = f"ap-real-binary-diagnostic-execution-{suffix}"

    review_rel = (
        f"examples/sandbox/asset-candidate-review-packets/"
        f"pytest-ap-source-file-review-{suffix}.json"
    )
    review_abs = REPO_ROOT / review_rel
    write_json(
        review_abs,
        {
            "schema_version": "1.0.0",
            "review_packet_id": review_packet_id,
            "source_inventory_id": f"asset-inventory-{suffix}",
            "candidate_id": f"candidate-{suffix}",
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "candidate_relative_path": source_rel,
            "candidate_extension": ".fbx",
            "candidate_category": "character_source",
            "size_bytes": source_abs.stat().st_size,
            "sha256": source_hash,
            "last_write_time_utc": "2026-05-05T00:00:00Z",
            "confidence": "high",
            "evidence_links": {"candidate": source_rel},
            "provenance_links": [],
            "material_texture_links": [],
            "warnings": [],
            "safety_summary": "review packet fixture",
            "recommended_next_step": "inspect_candidate",
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
            ],
            "output_path": review_rel,
            "created_utc": "2026-05-05T00:00:00Z",
        },
    )

    proposal_rel = (
        f"examples/sandbox/product-resolution-proposals/"
        f"pytest-ap-source-file-proposal-{suffix}.json"
    )
    proposal_abs = REPO_ROOT / proposal_rel
    write_json(
        proposal_abs,
        {
            "schema_version": "1.0.0",
            "proposal_id": proposal_id,
            "source_review_packet_id": review_packet_id,
            "source_inventory_id": f"asset-inventory-{suffix}",
            "source_project_inventory_id": project_id,
            "candidate_id": f"candidate-{suffix}",
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "candidate_relative_path": source_rel,
            "candidate_extension": ".fbx",
            "candidate_category": "character_source",
            "candidate_sha256": source_hash,
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
            "safety_summary": "proposal only fixture",
            "explicit_non_admissions": [
                "authoritative_writes",
                "product_resolution",
                "asset_id_claims",
                "source_uuid_claims",
                "spawning",
                "publishing",
                "o3de_editor_execution",
                "asset_processor_execution",
            ],
            "output_path": proposal_rel,
            "created_utc": "2026-05-05T00:00:00Z",
        },
    )

    ap_binary_preflight_rel = (
        f"examples/sandbox/ap-binary-preflights/"
        f"pytest-ap-source-file-binary-preflight-{suffix}.json"
    )
    ap_binary_preflight_abs = REPO_ROOT / ap_binary_preflight_rel
    write_json(
        ap_binary_preflight_abs,
        {
            "schema_version": "1.0.0",
            "ap_binary_preflight_id": preflight_id,
            "source_discovery_id": f"ap-binary-discovery-{suffix}",
            "source_ap_execution_preflight_id": f"ap-execution-preflight-{suffix}",
            "sandbox_root": "examples/sandbox",
            "selected_binary_path": binary_rel,
            "binary_kind": "AssetProcessorBatch",
            "binary_exists": True,
            "binary_allowed_for_future_execution_request": True,
            "execution_admitted": False,
            "required_manual_confirmation": True,
            "local_only": True,
            "readiness_status": "ready_for_future_real_ap_execution_request",
            "blocking_reasons": [],
            "warnings": [],
            "safety_summary": "binary preflight fixture",
            "explicit_non_admissions": [
                "authoritative_writes",
                "asset_processor_execution",
                "real_asset_processor_execution",
                "o3de_editor_execution",
            ],
            "output_path": ap_binary_preflight_rel,
            "created_utc": "2026-05-05T00:00:00Z",
        },
    )

    project_rel = (
        f"examples/sandbox/project-inventory/"
        f"pytest-ap-source-file-project-{suffix}.json"
    )
    project_abs = REPO_ROOT / project_rel
    write_json(
        project_abs,
        {
            "schema_version": "1.0.0",
            "inventory_id": project_id,
            "project_root": ".",
            "sandbox_root": "examples/sandbox",
            "project_json_path": "project.json",
            "project_name": "pytest-project",
            "known_asset_folders": [generated_rel],
            "generated_asset_candidate_folders": [generated_rel],
            "sandbox_evidence_folders": ["examples/sandbox"],
            "gem_names": [],
            "configured_non_executed_path_hints": [],
            "read_only_project_scan": True,
            "explicit_non_admissions": [
                "authoritative_writes",
                "asset_processor_execution",
                "o3de_editor_execution",
            ],
            "output_path": project_rel,
            "created_utc": "2026-05-05T00:00:00Z",
        },
    )

    real_diag_rel = ""
    real_diag_abs = None
    if include_real_diagnostic:
        real_diag_rel = (
            f"examples/sandbox/ap-real-binary-diagnostic-executions/"
            f"pytest-ap-source-file-real-diagnostic-{suffix}.json"
        )
        real_diag_abs = REPO_ROOT / real_diag_rel
        write_json(
            real_diag_abs,
            {
                "schema_version": "1.0.0",
                "real_binary_diagnostic_execution_id": real_diag_id,
                "source_ap_binary_preflight_id": preflight_id,
                "sandbox_root": "examples/sandbox",
                "selected_binary_path": binary_rel,
                "binary_kind": "AssetProcessorBatch",
                "execution_mode": "RealBinaryDiagnosticOnly",
                "approved_by_flag": True,
                "diagnostic_argument": "--version",
                "command_display": f'"{binary_rel}" --version',
                "command_executed": True,
                "command_allowlisted": True,
                "local_only": True,
                "timeout_seconds": 30,
                "exit_code": 0,
                "stdout_path": "",
                "stderr_path": "",
                "stdout_sha256": "",
                "stderr_sha256": "",
                "execution_status": "succeeded",
                "blocked_reason": "",
                "product_ids_claimed": False,
                "asset_ids_claimed": False,
                "source_uuids_claimed": False,
                "product_resolution_claimed": False,
                "cache_access_admitted": False,
                "live_database_access_admitted": False,
                "spawn_admitted": False,
                "publish_admitted": False,
                "explicit_non_admissions": ["authoritative_writes"],
                "output_path": real_diag_rel,
                "started_utc": "2026-05-05T00:00:00Z",
                "completed_utc": "2026-05-05T00:00:01Z",
            },
        )

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "source_abs": source_abs,
        "source_rel": source_rel,
        "binary_abs": binary_abs,
        "binary_rel": binary_rel,
        "review_abs": review_abs,
        "review_rel": review_rel,
        "proposal_abs": proposal_abs,
        "proposal_rel": proposal_rel,
        "ap_binary_preflight_abs": ap_binary_preflight_abs,
        "ap_binary_preflight_rel": ap_binary_preflight_rel,
        "project_abs": project_abs,
        "project_rel": project_rel,
        "real_diag_abs": real_diag_abs,
        "real_diag_rel": real_diag_rel,
    }


def cleanup_context(ctx: dict) -> None:
    preflight_root = REPO_ROOT / "examples/sandbox/ap-source-file-diagnostic-preflights"
    bundle_root = REPO_ROOT / "examples/sandbox/ap-source-file-diagnostic-preflight-bundles"

    for path in preflight_root.glob(f"*{ctx['suffix']}*.json"):
        remove_if_exists(path)

    for path in bundle_root.glob(f"*{ctx['suffix']}*"):
        if path.is_dir():
            remove_if_exists(path)

    for path in (
        ctx["review_abs"],
        ctx["proposal_abs"],
        ctx["ap_binary_preflight_abs"],
        ctx["project_abs"],
        ctx["real_diag_abs"],
        ctx["source_abs"],
        ctx["binary_abs"],
    ):
        if isinstance(path, Path):
            remove_if_exists(path)

    remove_if_exists(ctx["generated_abs"])


def build_preflight(ctx: dict, *extra: str) -> subprocess.CompletedProcess[str]:
    args = [
        "-ReviewPacketPath",
        ctx["review_rel"],
        "-ProposalPath",
        ctx["proposal_rel"],
        "-ApBinaryPreflightPath",
        ctx["ap_binary_preflight_rel"],
        "-ProjectInventoryPath",
        ctx["project_rel"],
    ]
    if ctx["real_diag_rel"]:
        args.extend(["-RealBinaryDiagnosticExecutionPath", ctx["real_diag_rel"]])
    args.extend(extra)
    return run_powershell_script(PREFLIGHT_BUILD_SCRIPT, *args)


def test_source_file_preflight_build_valid_supports_optional_real_diag_and_is_non_executing():
    ctx = make_source_file_preflight_context(include_real_diagnostic=True)
    try:
        output_rel = (
            "examples/sandbox/ap-source-file-diagnostic-preflights/"
            f"pytest-ap-source-file-preflight-{ctx['suffix']}.json"
        )
        output_abs = REPO_ROOT / output_rel

        source_hash_before = hashlib.sha256(ctx["source_abs"].read_bytes()).hexdigest()
        binary_hash_before = hashlib.sha256(ctx["binary_abs"].read_bytes()).hexdigest()

        result = build_preflight(ctx, "-OutputPath", output_rel)
        assert result.returncode == 0, result.stderr
        assert output_abs.exists()

        payload = read_json(output_abs)
        assert payload["output_path"].startswith(
            "examples/sandbox/ap-source-file-diagnostic-preflights/"
        )
        assert payload["source_review_packet_id"]
        assert payload["source_proposal_id"]
        assert payload["source_ap_binary_preflight_id"]
        assert payload["source_real_binary_diagnostic_execution_id"]
        assert payload["source_project_inventory_id"]

        assert payload["required_manual_confirmation"] is True
        assert payload["local_only"] is True
        assert payload["execution_admitted"] is False
        assert payload["ready_for_future_execution_request"] in {True, False}
        assert payload["readiness_status"] in {
            "blocked_missing_evidence",
            "blocked_safety_boundary",
            "ready_for_future_source_file_diagnostic_request",
            "rejected",
        }

        command = payload["proposed_diagnostic_command_display"]
        assert "--source-file" in command
        assert payload["candidate_relative_path"] in command
        assert "--mode source_file_diagnostic_display_only" in command
        assert "--no-execution" in command
        assert "|" not in command
        assert ";" not in command
        assert ">" not in command
        assert "<" not in command
        assert "--scan" not in command.lower()
        assert "scanfolder" not in command.lower()

        assert hashlib.sha256(ctx["source_abs"].read_bytes()).hexdigest() == source_hash_before
        assert hashlib.sha256(ctx["binary_abs"].read_bytes()).hexdigest() == binary_hash_before

        remove_if_exists(output_abs)
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_blocks_outside_and_traversal_inputs(tmp_path: Path):
    ctx = make_source_file_preflight_context(include_real_diagnostic=False)
    try:
        outside_review = tmp_path / f"outside-review-{ctx['suffix']}.json"
        outside_review.write_text("{}", encoding="utf-8")

        blocked_outside = run_powershell_script(
            PREFLIGHT_BUILD_SCRIPT,
            "-ReviewPacketPath",
            str(outside_review),
            "-ProposalPath",
            ctx["proposal_rel"],
            "-ApBinaryPreflightPath",
            ctx["ap_binary_preflight_rel"],
            "-ProjectInventoryPath",
            ctx["project_rel"],
        )
        assert blocked_outside.returncode != 0

        blocked_traversal_input = run_powershell_script(
            PREFLIGHT_BUILD_SCRIPT,
            "-ReviewPacketPath",
            "../outside/review.json",
            "-ProposalPath",
            ctx["proposal_rel"],
            "-ApBinaryPreflightPath",
            ctx["ap_binary_preflight_rel"],
            "-ProjectInventoryPath",
            ctx["project_rel"],
        )
        assert blocked_traversal_input.returncode != 0

        blocked_traversal_output = build_preflight(
            ctx,
            "-OutputPath",
            "../outside/preflight.json",
        )
        assert blocked_traversal_output.returncode != 0
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_rejects_forbidden_readiness_statuses():
    ctx = make_source_file_preflight_context(include_real_diagnostic=False)
    try:
        blocked = build_preflight(ctx, "-ReadinessStatus", "executed")
        assert blocked.returncode != 0
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_blocks_unsafe_tokens_cache_assetdb_and_wildcard_candidate_scope():
    ctx = make_source_file_preflight_context(include_real_diagnostic=False)
    try:
        scenarios = [
            (
                {"selected_binary_path": f"{ctx['binary_rel']}|whoami"},
                "selected_binary_path_contains_shell_operators",
            ),
            (
                {"selected_binary_path": "Cache/project/AssetProcessorBatch.exe"},
                "selected_binary_path_references_cache",
            ),
            (
                {"selected_binary_path": "assetdb.sqlite"},
                "selected_binary_path_references_database",
            ),
        ]

        for updates, expected_reason in scenarios:
            mutate_json(
                ctx["ap_binary_preflight_abs"],
                {
                    "selected_binary_path": ctx["binary_rel"],
                    "binary_exists": True,
                    "binary_allowed_for_future_execution_request": True,
                    "binary_kind": "AssetProcessorBatch",
                    "required_manual_confirmation": True,
                    "local_only": True,
                    "execution_admitted": False,
                    "readiness_status": "ready_for_future_real_ap_execution_request",
                    **updates,
                },
            )

            output_rel = (
                "examples/sandbox/ap-source-file-diagnostic-preflights/"
                f"pytest-ap-source-file-preflight-safety-{ctx['suffix']}-{uuid.uuid4().hex}.json"
            )
            result = build_preflight(ctx, "-OutputPath", output_rel)
            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            assert payload["execution_admitted"] is False
            assert payload["readiness_status"] == "blocked_safety_boundary"
            assert expected_reason in payload["blocking_reasons"]
            remove_if_exists(REPO_ROOT / payload["output_path"])

        mutate_json(
            ctx["review_abs"],
            {
                "candidate_relative_path": "scripts/generated/*.fbx",
            },
        )
        mutate_json(
            ctx["proposal_abs"],
            {
                "candidate_relative_path": "scripts/generated/*.fbx",
            },
        )

        wildcard_output_rel = (
            "examples/sandbox/ap-source-file-diagnostic-preflights/"
            f"pytest-ap-source-file-preflight-wildcard-{ctx['suffix']}.json"
        )
        wildcard_result = build_preflight(ctx, "-OutputPath", wildcard_output_rel)
        assert wildcard_result.returncode == 0, wildcard_result.stderr
        wildcard_payload = json.loads(wildcard_result.stdout)
        assert wildcard_payload["readiness_status"] == "blocked_safety_boundary"
        assert (
            "candidate_relative_path_must_be_single_file_not_wildcard"
            in wildcard_payload["blocking_reasons"]
        )
        remove_if_exists(REPO_ROOT / wildcard_payload["output_path"])
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_inspect_is_read_only():
    ctx = make_source_file_preflight_context(include_real_diagnostic=True)
    try:
        output_rel = (
            "examples/sandbox/ap-source-file-diagnostic-preflights/"
            f"pytest-ap-source-file-preflight-inspect-{ctx['suffix']}.json"
        )
        output_abs = REPO_ROOT / output_rel

        create = build_preflight(ctx, "-OutputPath", output_rel)
        assert create.returncode == 0, create.stderr

        payload = read_json(output_abs)
        preflight_hash_before = hashlib.sha256(output_abs.read_bytes()).hexdigest()
        review_hash_before = hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest()

        listed = run_powershell_script(PREFLIGHT_INSPECT_SCRIPT, "-List")
        assert listed.returncode == 0
        assert json.loads(listed.stdout)["preflight_count"] >= 1

        by_id = run_powershell_script(
            PREFLIGHT_INSPECT_SCRIPT,
            "-PreflightId",
            payload["source_file_diagnostic_preflight_id"],
            "-ShowRequirements",
            "-ShowBlockingReasons",
        )
        assert by_id.returncode == 0

        by_path = run_powershell_script(
            PREFLIGHT_INSPECT_SCRIPT,
            "-PreflightPath",
            output_rel,
        )
        assert by_path.returncode == 0

        assert hashlib.sha256(output_abs.read_bytes()).hexdigest() == preflight_hash_before
        assert hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest() == review_hash_before

        remove_if_exists(output_abs)
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_bundle_exports_json_snapshots_only_and_blocks_traversal():
    ctx = make_source_file_preflight_context(include_real_diagnostic=True)
    try:
        output_rel = (
            "examples/sandbox/ap-source-file-diagnostic-preflights/"
            f"pytest-ap-source-file-preflight-bundle-{ctx['suffix']}.json"
        )
        output_abs = REPO_ROOT / output_rel
        bundle_rel = (
            "examples/sandbox/ap-source-file-diagnostic-preflight-bundles/"
            f"pytest-ap-source-file-bundle-{ctx['suffix']}/bundle.manifest.json"
        )
        bundle_abs = REPO_ROOT / bundle_rel
        bundle_dir = bundle_abs.parent

        create = build_preflight(ctx, "-OutputPath", output_rel)
        assert create.returncode == 0, create.stderr
        assert output_abs.exists()

        source_hashes = {
            "preflight": hashlib.sha256(output_abs.read_bytes()).hexdigest(),
            "review": hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest(),
            "proposal": hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest(),
            "binary_preflight": hashlib.sha256(
                ctx["ap_binary_preflight_abs"].read_bytes()
            ).hexdigest(),
            "project": hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest(),
        }

        bundle = run_powershell_script(
            PREFLIGHT_BUNDLE_SCRIPT,
            "-PreflightPath",
            output_rel,
            "-BundlePath",
            bundle_rel,
        )
        assert bundle.returncode == 0, bundle.stderr
        assert bundle_abs.exists()

        manifest = read_json(bundle_abs)
        assert manifest["bundle_path"].startswith(
            "examples/sandbox/ap-source-file-diagnostic-preflight-bundles/"
        )
        for rel in manifest["copied_artifact_paths"]:
            assert rel.startswith(
                "examples/sandbox/ap-source-file-diagnostic-preflight-bundles/"
            )
            assert rel.lower().endswith(".json")

        copied_names = {p.name.lower() for p in bundle_dir.rglob("*") if p.is_file()}
        assert ctx["source_abs"].name.lower() not in copied_names
        assert ctx["binary_abs"].name.lower() not in copied_names

        assert hashlib.sha256(output_abs.read_bytes()).hexdigest() == source_hashes["preflight"]
        assert (
            hashlib.sha256(ctx["review_abs"].read_bytes()).hexdigest()
            == source_hashes["review"]
        )
        assert (
            hashlib.sha256(ctx["proposal_abs"].read_bytes()).hexdigest()
            == source_hashes["proposal"]
        )
        assert (
            hashlib.sha256(ctx["ap_binary_preflight_abs"].read_bytes()).hexdigest()
            == source_hashes["binary_preflight"]
        )
        assert (
            hashlib.sha256(ctx["project_abs"].read_bytes()).hexdigest()
            == source_hashes["project"]
        )

        blocked = run_powershell_script(
            PREFLIGHT_BUNDLE_SCRIPT,
            "-PreflightPath",
            output_rel,
            "-BundlePath",
            "../outside/bundle.manifest.json",
        )
        assert blocked.returncode != 0

        remove_if_exists(bundle_dir)
        remove_if_exists(output_abs)
    finally:
        cleanup_context(ctx)


def test_source_file_preflight_global_safety_boundaries_remain_blocked():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        PREFLIGHT_BUILD_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + PREFLIGHT_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + PREFLIGHT_BUNDLE_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )

    for forbidden in (
        "o3de.exe",
        "editor.exe",
        "invoke-expression",
        "start-process",
        "invoke-maxineauthoritativeresolverwrite.ps1",
    ):
        assert forbidden not in combined

    matrix = read_json(REPO_ROOT / "examples/capabilities/maxine-capability-matrix.json")
    caps = matrix["capabilities"]

    assert caps["ap_source_file_diagnostic_preflight_build"] == "sandbox_only"
    assert caps["ap_source_file_diagnostic_preflight_inspect"] == "read_only"
    assert caps["ap_source_file_diagnostic_preflight_bundle_export"] == "sandbox_only"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["real_asset_processor_execution"] == "blocked"
    assert caps["ap_source_file_processing_execution"] == "blocked"
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


def test_sandbox_writer_safety_verifier_passes_for_source_file_preflight_slice():
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
