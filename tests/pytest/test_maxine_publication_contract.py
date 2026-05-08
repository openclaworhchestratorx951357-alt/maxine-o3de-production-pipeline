import json
from pathlib import Path

from tools.qc.publication_contract import validate_publication_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
DRAFT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "draft_mesh.pass.example.json"
RELEASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_draft_package_may_pass_with_azmodel_and_smoke_evidence():
    result = validate_publication_contract(_load(DRAFT_MANIFEST), strict=True)

    assert result.status == "pass"


def test_release_package_requires_prefab_or_procprefab_ref():
    manifest = _load(RELEASE_MANIFEST)
    manifest["publication"]["package"].pop("prefab_ref")

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "procprefab" in " ".join(result.messages)


def test_release_package_cannot_pass_with_spawn_only_evidence():
    manifest = _load(RELEASE_MANIFEST)
    manifest["publication"]["package"]["prefab_ref"] = ""
    manifest["evidence"]["refs"] = [{"id": "spawn-only", "kind": "spawn", "path": "examples/production/spawn-only.json"}]

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "spawn-only" in " ".join(result.messages)


def test_release_package_refuses_cache_only_product_evidence():
    manifest = _load(RELEASE_MANIFEST)
    for product in manifest["o3de"]["actual_products"]:
        product["evidence_source"] = "cache_heuristic"
        product["produced_by_source_uuid"] = False
    manifest["o3de"]["product_resolution"]["cache_heuristic_used"] = True

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.error_codes


def test_undo_plan_required():
    manifest = _load(RELEASE_MANIFEST)
    manifest["undo"] = {}

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "MXN_UNDO_PLAN_MISSING" in result.error_codes


def test_evidence_bundle_required():
    manifest = _load(RELEASE_MANIFEST)
    manifest["evidence"]["bundle_ref"] = ""

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "evidence bundle" in " ".join(result.messages)
