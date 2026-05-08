from tools.o3de.product_matrix_resolver import validate_expected_products
from tools.o3de.product_resolver import FixtureProductResolver, ProductRecord


def _product(product_type: str, path: str | None = None, status: str = "ready") -> ProductRecord:
    return ProductRecord(
        product_type=product_type,
        product_path=path or f"Cache/pc/maxine.{product_type}",
        platform="pc",
        status=status,
    )


def test_draft_mesh_with_azmodel_passes():
    result = validate_expected_products("draft_mesh", [_product("azmodel")], strict=True)

    assert result.status == "pass"
    assert result.error_codes == []


def test_release_rigged_missing_actor_fails():
    result = validate_expected_products(
        "release_rigged",
        [_product("motion"), _product("motionset"), _product("animgraph"), _product("procprefab")],
        strict=True,
    )

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.error_codes
    assert "actor" in " ".join(result.messages)


def test_release_rigged_missing_motion_fails():
    result = validate_expected_products(
        "release_rigged",
        [_product("actor"), _product("motionset"), _product("animgraph"), _product("procprefab")],
        strict=True,
    )

    assert result.status == "fail"
    assert "motion" in " ".join(result.messages)


def test_pending_products_fail_in_strict_mode():
    result = validate_expected_products(
        "release_rigged",
        [
            _product("actor"),
            _product("motion"),
            _product("motionset"),
            _product("animgraph"),
            _product("procprefab", status="pending"),
        ],
        strict=True,
    )

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCTS_PENDING" in result.error_codes


def test_unknown_product_type_fails_clearly():
    result = validate_expected_products("draft_mesh", [_product("azmodel"), _product("mystery")])

    assert result.status == "fail"
    assert "unknown product type" in " ".join(result.messages)


def test_cache_heuristic_use_fails_in_release_mode():
    result = validate_expected_products(
        "release_rigged",
        [_product("actor"), _product("motion"), _product("motionset"), _product("animgraph"), _product("procprefab")],
        cache_heuristic_used=True,
    )

    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.error_codes


def test_fixture_resolver_lists_products_by_source_uuid():
    resolver = FixtureProductResolver(
        sources=[
            {
                "source_uuid": "source-001",
                "source_path": "Assets/Characters/maxine/maxine.fbx",
                "products": [
                    {"product_type": "actor", "product_path": "Cache/pc/maxine.actor", "platform": "pc", "status": "ready"}
                ],
            }
        ]
    )

    products = resolver.list_products_by_source_uuid("source-001")

    assert [product.product_type for product in products] == ["actor"]
