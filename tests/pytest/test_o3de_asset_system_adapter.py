import json
import os
import subprocess
import sys
from pathlib import Path

from tools.o3de.product_resolver import (
    FixtureAssetSystemAdapter,
    LocalO3DEAssetSystemAdapter,
    resolve_manifest_products,
    select_asset_system_adapter,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DRAFT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "draft_mesh.pass.example.json"
RELEASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"
PRODUCT_RESOLVER = REPO_ROOT / "tools" / "o3de" / "product_resolver.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_default_resolver_mode_is_fixture_offline(monkeypatch):
    monkeypatch.delenv("MAXINE_ENABLE_O3DE_INTEGRATION", raising=False)

    adapter = select_asset_system_adapter()
    result = resolve_manifest_products(_load(RELEASE_MANIFEST))

    assert isinstance(adapter, FixtureAssetSystemAdapter)
    assert result.mode == "fixture"
    assert result.integration_executed is False
    assert result.live_o3de_execution is False
    assert result.cache_heuristic_used is False


def test_fixture_output_is_stable_across_repeated_runs():
    manifest = _load(RELEASE_MANIFEST)

    first = resolve_manifest_products(manifest).to_payload()
    second = resolve_manifest_products(manifest).to_payload()

    assert first == second


def test_fixture_resolver_passes_known_good_draft_and_release():
    draft = resolve_manifest_products(_load(DRAFT_MANIFEST))
    release = resolve_manifest_products(_load(RELEASE_MANIFEST))

    assert draft.status == "pass"
    assert [product.product_type for product in draft.products] == ["azmodel"]
    assert release.status == "pass"
    assert {"actor", "motion", "motionset", "animgraph", "procprefab"}.issubset(
        {product.product_type for product in release.products}
    )


def test_fixture_resolver_fails_missing_products_with_stable_error_code():
    manifest = _load(RELEASE_MANIFEST)
    manifest["o3de"]["actual_products"] = [
        product for product in manifest["o3de"]["actual_products"] if product["product_type"] != "actor"
    ]

    result = resolve_manifest_products(manifest)

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.errors
    assert "actor" in result.missing_expected_product_types


def test_release_cache_heuristic_resolver_result_is_invalid():
    manifest = _load(RELEASE_MANIFEST)
    manifest["o3de"]["product_resolution"]["cache_heuristic_used"] = True

    result = resolve_manifest_products(manifest)

    assert result.mode == "invalid"
    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.errors


def test_local_o3de_gate_on_tooling_unavailable_skips_without_strict(tmp_path, monkeypatch):
    monkeypatch.delenv("O3DE_ENGINE_ROOT", raising=False)
    monkeypatch.delenv("O3DE_PROJECT_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))

    adapter = LocalO3DEAssetSystemAdapter(env=os.environ, path_entries=[str(tmp_path)])
    result = adapter.resolve_manifest_products(_load(RELEASE_MANIFEST), strict_integration=False)

    assert result.mode == "unavailable"
    assert result.status == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.warnings
    assert result.integration_executed is False
    assert result.live_o3de_execution is False


def test_local_o3de_gate_on_tooling_unavailable_fails_in_strict_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("O3DE_ENGINE_ROOT", raising=False)
    monkeypatch.delenv("O3DE_PROJECT_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))

    adapter = LocalO3DEAssetSystemAdapter(env=os.environ, path_entries=[str(tmp_path)])
    result = adapter.resolve_manifest_products(_load(RELEASE_MANIFEST), strict_integration=True)

    assert result.mode == "unavailable"
    assert result.status == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.errors


def test_resolver_result_serializes_manifest_evidence_fields():
    result = resolve_manifest_products(_load(RELEASE_MANIFEST))

    evidence = result.to_manifest_evidence()

    assert evidence["resolver_mode"] == "fixture"
    assert evidence["integration_executed"] is False
    assert evidence["live_o3de_execution"] is False
    assert evidence["fixture_data_used"] is True
    assert evidence["cache_heuristic_used"] is False
    assert evidence["evidence_refs"]


def test_product_resolver_cli_defaults_to_fixture_pass():
    result = subprocess.run(
        [sys.executable, str(PRODUCT_RESOLVER), "--manifest", str(RELEASE_MANIFEST)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "fixture"
    assert payload["status"] == "pass"
    assert payload["integration_executed"] is False
    assert payload["live_o3de_execution"] is False


def test_validate_all_integration_gate_skips_missing_o3de_without_strict(tmp_path, monkeypatch):
    env = os.environ.copy()
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env["PATH"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL), "--enable-o3de-integration"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "local O3DE integration: skipped" in result.stdout
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout


def test_validate_all_strict_integration_fails_missing_o3de(tmp_path):
    env = os.environ.copy()
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env["PATH"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL), "--enable-o3de-integration", "--strict-integration"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "local O3DE integration: fail" in result.stdout
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
