import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY_PREFLIGHT_BUILD_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApBinaryPreflightBuild.ps1"
)
REAL_DIAG_EXEC_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApRealBinaryDiagnosticExecution.ps1"
)
REAL_DIAG_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineApRealBinaryDiagnosticInspect.ps1"
)
REAL_DIAG_BUNDLE_SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "powershell"
    / "Invoke-MaxineApRealBinaryDiagnosticBundleExport.ps1"
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


def make_binary_preflight_context() -> dict:
    suffix = uuid.uuid4().hex

    generated_rel = f"scripts/generated/pytest-ap-real-binary-{suffix}"
    generated_abs = REPO_ROOT / generated_rel
    generated_abs.mkdir(parents=True, exist_ok=True)

    fake_binary_rel = f"{generated_rel}/AssetProcessorBatch.exe"
    fake_binary_abs = REPO_ROOT / fake_binary_rel
    fake_binary_abs.write_text("fake-ap-binary-fixture", encoding="utf-8")

    discovery_rel = f"examples/sandbox/ap-binary-discovery/pytest-ap-real-binary-discovery-{suffix}.json"
    discovery_abs = REPO_ROOT / discovery_rel
    write_json(
        discovery_abs,
        {
            "schema_version": "1.0.0",
            "discovery_id": f"ap-binary-discovery-{suffix}",
            "sandbox_root": "examples/sandbox",
            "read_only": True,
            "execution_admitted": False,
            "existing_candidates": [
                {
                    "candidate_path": fake_binary_rel,
                    "path_source": "explicit",
                    "exists": True,
                }
            ],
            "rejected_candidates": [],
            "output_path": discovery_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    ap_execution_preflight_rel = (
        f"examples/sandbox/ap-execution-preflights/pytest-ap-real-binary-ap-preflight-{suffix}.json"
    )
    ap_execution_preflight_abs = REPO_ROOT / ap_execution_preflight_rel
    write_json(
        ap_execution_preflight_abs,
        {
            "schema_version": "1.0.0",
            "preflight_id": f"ap-execution-preflight-{suffix}",
            "sandbox_root": "examples/sandbox",
            "required_manual_confirmation": True,
            "local_only": True,
            "execution_admitted": False,
            "readiness_status": "ready_for_future_execution_request",
            "proposed_ap_command_display": "ap_batch_display_only --project-root . --candidate scripts/generated/mock.fbx --mode preflight_display_only --no_execution",
            "output_path": ap_execution_preflight_rel,
            "created_utc": "2026-05-04T00:00:00Z",
        },
    )

    binary_preflight_rel = f"examples/sandbox/ap-binary-preflights/pytest-ap-real-binary-preflight-{suffix}.json"
    binary_preflight_abs = REPO_ROOT / binary_preflight_rel

    build = run_powershell_script(
        BINARY_PREFLIGHT_BUILD_SCRIPT,
        "-DiscoveryPath",
        discovery_rel,
        "-ApExecutionPreflightPath",
        ap_execution_preflight_rel,
        "-OutputPath",
        binary_preflight_rel,
    )
    assert build.returncode == 0, build.stderr
    assert binary_preflight_abs.exists()

    return {
        "suffix": suffix,
        "generated_abs": generated_abs,
        "generated_rel": generated_rel,
        "fake_binary_abs": fake_binary_abs,
        "fake_binary_rel": fake_binary_rel,
        "discovery_abs": discovery_abs,
        "discovery_rel": discovery_rel,
        "ap_execution_preflight_abs": ap_execution_preflight_abs,
        "ap_execution_preflight_rel": ap_execution_preflight_rel,
        "binary_preflight_abs": binary_preflight_abs,
        "binary_preflight_rel": binary_preflight_rel,
    }


def cleanup_context(ctx: dict) -> None:
    execution_root = REPO_ROOT / "examples/sandbox/ap-real-binary-diagnostic-executions"
    bundle_root = REPO_ROOT / "examples/sandbox/ap-real-binary-diagnostic-bundles"

    for file_path in execution_root.glob(f"*{ctx['suffix']}*.json"):
        try:
            payload = read_json(file_path)
            stdout_rel = payload.get("stdout_path", "")
            stderr_rel = payload.get("stderr_path", "")
            if isinstance(stdout_rel, str) and stdout_rel:
                remove_if_exists(REPO_ROOT / stdout_rel)
            if isinstance(stderr_rel, str) and stderr_rel:
                remove_if_exists(REPO_ROOT / stderr_rel)
        except Exception:
            pass
        remove_if_exists(file_path)

    for bundle_dir in bundle_root.glob(f"*{ctx['suffix']}*"):
        if bundle_dir.is_dir():
            remove_if_exists(bundle_dir)

    for path in (
        ctx["binary_preflight_abs"],
        ctx["ap_execution_preflight_abs"],
        ctx["discovery_abs"],
        ctx["fake_binary_abs"],
    ):
        remove_if_exists(path)

    remove_if_exists(ctx["generated_abs"])


def mutate_binary_preflight(preflight_abs: Path, updates: dict) -> None:
    payload = read_json(preflight_abs)
    payload.update(updates)
    write_json(preflight_abs, payload)


def run_real_diag(
    binary_preflight_rel: str,
    suffix: str,
    *args: str,
) -> tuple[subprocess.CompletedProcess[str], str, Path]:
    execution_rel = (
        "examples/sandbox/ap-real-binary-diagnostic-executions/"
        f"pytest-ap-real-binary-execution-{suffix}-{uuid.uuid4().hex}.json"
    )
    execution_abs = REPO_ROOT / execution_rel
    result = run_powershell_script(
        REAL_DIAG_EXEC_SCRIPT,
        "-ApBinaryPreflightPath",
        binary_preflight_rel,
        "-OutputPath",
        execution_rel,
        *args,
    )
    return result, execution_rel, execution_abs


def test_real_binary_diag_blocks_without_approval_flag():
    ctx = make_binary_preflight_context()
    try:
        result, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"], ctx["suffix"], "-UseSimulatedCommandMode"
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(result.stdout)
        assert payload["execution_status"] == "blocked"
        assert payload["command_executed"] is False
        assert "without approval flag" in payload["blocked_reason"]

        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_blocks_when_readiness_status_is_not_ready_for_future_real_ap_execution_request():
    ctx = make_binary_preflight_context()
    try:
        mutate_binary_preflight(
            ctx["binary_preflight_abs"],
            {"readiness_status": "blocked_missing_binary"},
        )

        result, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(result.stdout)
        assert payload["execution_status"] == "blocked"
        assert payload["command_executed"] is False
        assert "readiness_status" in payload["blocked_reason"]

        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_blocks_binary_existence_allowance_local_only_execution_admission_and_binary_kind():
    ctx = make_binary_preflight_context()
    try:
        scenarios = [
            ({"binary_exists": False}, "binary_exists must be true"),
            (
                {"binary_allowed_for_future_execution_request": False},
                "binary_allowed_for_future_execution_request must be true",
            ),
            ({"local_only": False}, "local_only must be true"),
            ({"execution_admitted": True}, "execution_admitted=true"),
            ({"binary_kind": "unknown"}, "binary_kind 'unknown' is not allowed"),
        ]

        for updates, expected in scenarios:
            mutate_binary_preflight(
                ctx["binary_preflight_abs"],
                {
                    "binary_exists": True,
                    "binary_allowed_for_future_execution_request": True,
                    "local_only": True,
                    "execution_admitted": False,
                    "binary_kind": "AssetProcessorBatch",
                    **updates,
                },
            )

            result, _, execution_abs = run_real_diag(
                ctx["binary_preflight_rel"],
                ctx["suffix"],
                "-ApproveRealBinaryDiagnosticExecution",
                "-UseSimulatedCommandMode",
            )
            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            assert payload["execution_status"] == "blocked"
            assert payload["command_executed"] is False
            assert expected in payload["blocked_reason"]
            remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_blocks_unsafe_diagnostic_argument():
    ctx = make_binary_preflight_context()
    try:
        result, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-DiagnosticArgument",
            "--list",
            "-UseSimulatedCommandMode",
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(result.stdout)
        assert payload["execution_status"] == "blocked"
        assert payload["command_executed"] is False
        assert (
            "diagnostic_argument '--list' is not allowlisted"
            in payload["blocked_reason"]
        )

        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_blocks_unsafe_command_display_and_cache_or_assetdb_paths():
    ctx = make_binary_preflight_context()
    try:
        mutate_binary_preflight(
            ctx["binary_preflight_abs"],
            {
                "selected_binary_path": f"{ctx['generated_rel']}/AssetProcessorBatch.exe|whoami",
            },
        )
        result_unsafe_display, _, execution_abs_unsafe_display = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
        )
        assert result_unsafe_display.returncode == 0, result_unsafe_display.stderr
        payload_unsafe_display = json.loads(result_unsafe_display.stdout)
        assert payload_unsafe_display["execution_status"] == "blocked"
        assert (
            "command display contains shell operators"
            in payload_unsafe_display["blocked_reason"]
        )

        mutate_binary_preflight(
            ctx["binary_preflight_abs"],
            {
                "selected_binary_path": "Cache/project/AssetProcessorBatch.exe",
            },
        )
        result_cache, _, execution_abs_cache = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
        )
        assert result_cache.returncode == 0, result_cache.stderr
        payload_cache = json.loads(result_cache.stdout)
        assert payload_cache["execution_status"] == "blocked"
        assert "includes Cache" in payload_cache["blocked_reason"]

        mutate_binary_preflight(
            ctx["binary_preflight_abs"],
            {
                "selected_binary_path": "assetdb.sqlite",
            },
        )
        result_db, _, execution_abs_db = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
        )
        assert result_db.returncode == 0, result_db.stderr
        payload_db = json.loads(result_db.stdout)
        assert payload_db["execution_status"] == "blocked"
        assert "assetdb.sqlite" in payload_db["blocked_reason"]

        remove_if_exists(execution_abs_unsafe_display)
        remove_if_exists(execution_abs_cache)
        remove_if_exists(execution_abs_db)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_succeeds_in_allowlisted_simulated_mode_and_records_hashes_flags_and_paths():
    ctx = make_binary_preflight_context()
    try:
        result, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
            "-DiagnosticArgument",
            "--version",
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(result.stdout)
        assert payload["execution_status"] == "succeeded"
        assert payload["command_executed"] is True
        assert payload["command_allowlisted"] is True
        assert payload["execution_mode"] == "RealBinaryDiagnosticOnly"
        assert payload["approved_by_flag"] is True
        assert payload["local_only"] is True
        assert payload["exit_code"] == 0

        assert payload["output_path"].startswith(
            "examples/sandbox/ap-real-binary-diagnostic-executions/"
        )
        assert payload["stdout_path"].startswith(
            "examples/sandbox/ap-real-binary-diagnostic-executions/"
        )
        assert payload["stderr_path"].startswith(
            "examples/sandbox/ap-real-binary-diagnostic-executions/"
        )

        stdout_abs = REPO_ROOT / payload["stdout_path"]
        stderr_abs = REPO_ROOT / payload["stderr_path"]
        assert stdout_abs.exists()
        assert stderr_abs.exists()

        assert (
            hashlib.sha256(stdout_abs.read_bytes()).hexdigest().upper()
            == payload["stdout_sha256"]
        )
        assert (
            hashlib.sha256(stderr_abs.read_bytes()).hexdigest().upper()
            == payload["stderr_sha256"]
        )

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
        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_timeout_is_bounded_and_recorded_in_simulation_mode():
    ctx = make_binary_preflight_context()
    try:
        result, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
            "-SimulateTimeout",
            "-TimeoutSeconds",
            "2",
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(result.stdout)
        assert payload["execution_status"] == "timed_out"
        assert payload["command_executed"] is True
        assert payload["exit_code"] == 124
        assert payload["timeout_seconds"] == 2

        stdout_abs = REPO_ROOT / payload["stdout_path"]
        stderr_abs = REPO_ROOT / payload["stderr_path"]
        assert stdout_abs.exists()
        assert stderr_abs.exists()

        remove_if_exists(stdout_abs)
        remove_if_exists(stderr_abs)
        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_inspect_is_read_only_and_bundle_exports_json_stdout_stderr_only():
    ctx = make_binary_preflight_context()
    try:
        create, _, execution_abs = run_real_diag(
            ctx["binary_preflight_rel"],
            ctx["suffix"],
            "-ApproveRealBinaryDiagnosticExecution",
            "-UseSimulatedCommandMode",
        )
        assert create.returncode == 0, create.stderr
        execution = json.loads(create.stdout)

        execution_hash_before = hashlib.sha256(execution_abs.read_bytes()).hexdigest()
        stdout_abs = REPO_ROOT / execution["stdout_path"]
        stderr_abs = REPO_ROOT / execution["stderr_path"]
        stdout_hash_before = hashlib.sha256(stdout_abs.read_bytes()).hexdigest()
        stderr_hash_before = hashlib.sha256(stderr_abs.read_bytes()).hexdigest()

        listed = run_powershell_script(REAL_DIAG_INSPECT_SCRIPT, "-List")
        assert listed.returncode == 0
        assert json.loads(listed.stdout)["execution_count"] >= 1

        by_id = run_powershell_script(
            REAL_DIAG_INSPECT_SCRIPT,
            "-ExecutionId",
            execution["real_binary_diagnostic_execution_id"],
            "-ShowOutputRefs",
            "-ShowBlockedReason",
        )
        assert by_id.returncode == 0

        assert hashlib.sha256(execution_abs.read_bytes()).hexdigest() == execution_hash_before
        assert hashlib.sha256(stdout_abs.read_bytes()).hexdigest() == stdout_hash_before
        assert hashlib.sha256(stderr_abs.read_bytes()).hexdigest() == stderr_hash_before

        bundle_rel = (
            "examples/sandbox/ap-real-binary-diagnostic-bundles/"
            f"pytest-ap-real-binary-{ctx['suffix']}/bundle.manifest.json"
        )
        bundle_abs = REPO_ROOT / bundle_rel
        bundle_dir = bundle_abs.parent

        bundle = run_powershell_script(
            REAL_DIAG_BUNDLE_SCRIPT,
            "-ExecutionPath",
            execution["output_path"],
            "-BundlePath",
            bundle_rel,
        )
        assert bundle.returncode == 0, bundle.stderr
        manifest = json.loads(bundle.stdout)

        assert bundle_abs.exists()
        assert manifest["bundle_path"].startswith(
            "examples/sandbox/ap-real-binary-diagnostic-bundles/"
        )
        for rel in manifest["copied_artifact_paths"]:
            assert rel.startswith("examples/sandbox/ap-real-binary-diagnostic-bundles/")
            lower = rel.lower()
            assert lower.endswith(".json") or lower.endswith(".txt")

        names = {p.name for p in bundle_dir.rglob("*") if p.is_file()}
        assert Path(ctx["fake_binary_rel"]).name not in names

        blocked_bundle = run_powershell_script(
            REAL_DIAG_BUNDLE_SCRIPT,
            "-ExecutionPath",
            execution["output_path"],
            "-BundlePath",
            "../outside/bundle.manifest.json",
        )
        assert blocked_bundle.returncode != 0

        remove_if_exists(bundle_dir)
        remove_if_exists(stdout_abs)
        remove_if_exists(stderr_abs)
        remove_if_exists(execution_abs)
    finally:
        cleanup_context(ctx)


def test_real_binary_diag_global_safety_boundaries_remain_blocked():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        REAL_DIAG_EXEC_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + REAL_DIAG_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + REAL_DIAG_BUNDLE_SCRIPT.read_text(encoding="utf-8-sig").lower()
    )

    for token in (
        "invoke-expression",
        "start-process",
        "o3de.exe",
        "editor.exe",
        "invoke-maxineauthoritativeresolverwrite.ps1",
    ):
        assert token not in combined

    matrix = read_json(REPO_ROOT / "examples/capabilities/maxine-capability-matrix.json")
    caps = matrix["capabilities"]
    assert caps["ap_real_binary_diagnostic_execution"] == "sandbox_only"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["real_asset_processor_execution"] == "blocked"
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
