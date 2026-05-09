"""Asset System product-resolution adapter contracts and fixture/local implementations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validation.maxine_paths import normalize_path_text


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"


@dataclass(frozen=True)
class ProductRecord:
    product_type: str
    product_path: str
    platform: str = "pc"
    status: str = "ready"
    source_uuid: str = ""
    asset_id: str = ""
    source_sub_id: str = ""
    relative_product_path: str = ""
    sha256: str = ""
    sha256_available: bool = False
    produced_by_source_uuid: bool = True
    evidence_source: str = "fixture"

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "ProductRecord":
        product_path = normalize_path_text(str(payload.get("product_path", payload.get("path", ""))).strip())
        relative_product_path = normalize_path_text(
            str(payload.get("relative_product_path", payload.get("relative_path", product_path))).strip()
        )
        sha256 = str(payload.get("sha256", "")).strip()
        return cls(
            product_type=str(payload.get("product_type", "")).strip(),
            product_path=product_path,
            platform=str(payload.get("platform", "pc")).strip() or "pc",
            status=str(payload.get("status", "ready")).strip() or "ready",
            source_uuid=str(payload.get("source_uuid", "")).strip(),
            asset_id=str(payload.get("asset_id", "")).strip(),
            source_sub_id=str(payload.get("source_sub_id", payload.get("sub_id", ""))).strip(),
            relative_product_path=relative_product_path,
            sha256=sha256,
            sha256_available=bool(payload.get("sha256_available", bool(sha256))),
            produced_by_source_uuid=bool(payload.get("produced_by_source_uuid", True)),
            evidence_source=str(payload.get("evidence_source", payload.get("source", "fixture"))).strip() or "fixture",
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "product_type": self.product_type,
            "product_path": self.product_path,
            "relative_product_path": self.relative_product_path or self.product_path,
            "platform": self.platform,
            "status": self.status,
            "source_uuid": self.source_uuid,
            "asset_id": self.asset_id,
            "source_sub_id": self.source_sub_id,
            "sha256": self.sha256,
            "sha256_available": self.sha256_available,
            "produced_by_source_uuid": self.produced_by_source_uuid,
            "evidence_source": self.evidence_source,
        }


@dataclass(frozen=True)
class SourceInfo:
    source_uuid: str
    source_path: str
    scan_folder: str = "Assets"
    project_name: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source_uuid": self.source_uuid,
            "source_path": self.source_path,
            "scan_folder": self.scan_folder,
            "project_name": self.project_name,
        }


@dataclass(frozen=True)
class PendingAssetRecord:
    source_path: str = ""
    source_uuid: str = ""
    platform: str = "pc"
    status: str = "pending"
    reason: str = ""
    evidence_source: str = "fixture"

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_uuid": self.source_uuid,
            "platform": self.platform,
            "status": self.status,
            "reason": self.reason,
            "evidence_source": self.evidence_source,
        }


@dataclass(frozen=True)
class AssetSystemResolverResult:
    mode: str
    status: str
    products: List[ProductRecord]
    pending_assets: List[PendingAssetRecord]
    missing_expected_product_types: List[str]
    warnings: List[str]
    errors: List[str]
    messages: List[str]
    source_reference: SourceInfo | None = None
    integration_executed: bool = False
    live_o3de_execution: bool = False
    cache_heuristic_used: bool = False
    evidence_refs: List[Dict[str, Any]] | None = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
            "source_reference": self.source_reference.to_payload() if self.source_reference else None,
            "products": [product.to_payload() for product in self.products],
            "pending_assets": [asset.to_payload() for asset in self.pending_assets],
            "missing_expected_product_types": list(self.missing_expected_product_types),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "messages": list(self.messages),
            "integration_executed": self.integration_executed,
            "live_o3de_execution": self.live_o3de_execution,
            "cache_heuristic_used": self.cache_heuristic_used,
            "evidence_refs": list(self.evidence_refs or []),
        }

    def to_manifest_evidence(self) -> Dict[str, Any]:
        return {
            "resolver_mode": self.mode,
            "status": self.status,
            "integration_executed": self.integration_executed,
            "live_o3de_execution": self.live_o3de_execution,
            "fixture_data_used": self.mode == "fixture",
            "cache_heuristic_used": self.cache_heuristic_used,
            "evidence_refs": list(self.evidence_refs or []),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


class ProductResolver(Protocol):
    def generate_relative_source_path(self, source_path: str) -> str: ...

    def list_asset_safe_folders(self) -> List[str]: ...

    def get_source_info_by_source_path(self, source_path: str) -> SourceInfo | None: ...

    def get_source_info_by_source_uuid(self, source_uuid: str) -> SourceInfo | None: ...

    def list_products_by_source_uuid(self, source_uuid: str) -> List[ProductRecord]: ...

    def report_pending_assets(self, platform: str) -> List[ProductRecord]: ...

    def request_reprocess(self, source_uuid: str) -> Dict[str, Any]: ...

    def clear_fingerprint(self, source_uuid: str) -> Dict[str, Any]: ...

    def resolve_manifest_products(
        self,
        manifest: Mapping[str, Any],
        *,
        platform: str = "pc",
        strict: bool = True,
        strict_integration: bool = False,
    ) -> AssetSystemResolverResult: ...


class FixtureProductResolver:
    """Deterministic resolver for tests and docs; never calls live O3DE services."""

    def __init__(self, sources: Iterable[Dict[str, Any]] | None = None, asset_safe_folders: Iterable[str] | None = None):
        self._asset_safe_folders = [normalize_path_text(path) for path in (asset_safe_folders or ["Assets"])]
        self._sources: Dict[str, SourceInfo] = {}
        self._sources_by_path: Dict[str, SourceInfo] = {}
        self._products: Dict[str, List[ProductRecord]] = {}
        for source in sources or []:
            source_uuid = str(source.get("source_uuid", "")).strip()
            source_path = normalize_path_text(str(source.get("source_path", "")).strip())
            if not source_uuid or not source_path:
                continue
            info = SourceInfo(source_uuid=source_uuid, source_path=source_path, scan_folder=str(source.get("scan_folder", "Assets")))
            self._sources[source_uuid] = info
            self._sources_by_path[source_path.lower()] = info
            products = []
            for product_payload in source.get("products", []):
                if isinstance(product_payload, dict):
                    product = ProductRecord.from_mapping({**product_payload, "source_uuid": source_uuid})
                    products.append(product)
            self._products[source_uuid] = products

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> "FixtureProductResolver":
        o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), Mapping) else {}
        inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), Mapping) else {}
        sources = inputs.get("sources", []) if isinstance(inputs.get("sources"), list) else []
        source_path = ""
        if sources and isinstance(sources[0], Mapping):
            source_path = str(sources[0].get("relative_path", sources[0].get("path", ""))).strip()
        source_uuid = str(o3de.get("source_uuid", "")).strip()
        products = o3de.get("actual_products", []) if isinstance(o3de.get("actual_products"), list) else []
        if not source_uuid or not source_path:
            return cls()
        return cls(
            sources=[
                {
                    "source_uuid": source_uuid,
                    "source_path": source_path,
                    "scan_folder": "Assets",
                    "products": products,
                }
            ]
        )

    def generate_relative_source_path(self, source_path: str) -> str:
        normalized = normalize_path_text(source_path)
        for folder in self._asset_safe_folders:
            marker = f"{folder.rstrip('/')}/"
            if marker.lower() in normalized.lower():
                idx = normalized.lower().index(marker.lower())
                return normalized[idx:]
        return normalized.lstrip("/")

    def list_asset_safe_folders(self) -> List[str]:
        return list(self._asset_safe_folders)

    def get_source_info_by_source_path(self, source_path: str) -> SourceInfo | None:
        return self._sources_by_path.get(self.generate_relative_source_path(source_path).lower())

    def get_source_info_by_source_uuid(self, source_uuid: str) -> SourceInfo | None:
        return self._sources.get(source_uuid)

    def list_products_by_source_uuid(self, source_uuid: str) -> List[ProductRecord]:
        return list(self._products.get(source_uuid, []))

    def report_pending_assets(self, platform: str) -> List[ProductRecord]:
        platform_norm = platform.lower()
        return [
            product
            for products in self._products.values()
            for product in products
            if product.platform.lower() == platform_norm and product.status != "ready"
        ]

    def request_reprocess(self, source_uuid: str) -> Dict[str, Any]:
        return {
            "supported": False,
            "source_uuid": source_uuid,
            "message": "Fixture resolver does not invoke Asset Processor reprocess.",
        }

    def clear_fingerprint(self, source_uuid: str) -> Dict[str, Any]:
        return {
            "supported": False,
            "source_uuid": source_uuid,
            "message": "Fixture resolver does not clear live Asset Processor fingerprints.",
        }

    def resolve_manifest_products(
        self,
        manifest: Mapping[str, Any],
        *,
        platform: str = "pc",
        strict: bool = True,
        strict_integration: bool = False,
    ) -> AssetSystemResolverResult:
        return _resolve_with_fixture_data(manifest, mode="fixture", platform=platform, strict=strict)


class FixtureAssetSystemAdapter(FixtureProductResolver):
    """Default offline adapter used by CI and local validation."""


class LocalO3DEAssetSystemAdapter:
    """Integration-gated read/query adapter stub for future local O3DE wiring."""

    TOOL_NAMES = ("AssetProcessorBatch.exe", "AssetProcessorBatch", "o3de.exe", "o3de")

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        path_entries: Sequence[str] | None = None,
    ) -> None:
        self._env = env if env is not None else os.environ
        if path_entries is None:
            path_entries = str(self._env.get("PATH", "")).split(os.pathsep)
        self._path_entries = [Path(entry) for entry in path_entries if str(entry).strip()]

    def generate_relative_source_path(self, source_path: str) -> str:
        return normalize_path_text(source_path).lstrip("/")

    def list_asset_safe_folders(self) -> List[str]:
        return ["Assets"]

    def get_source_info_by_source_path(self, source_path: str) -> SourceInfo | None:
        return None

    def get_source_info_by_source_uuid(self, source_uuid: str) -> SourceInfo | None:
        return None

    def list_products_by_source_uuid(self, source_uuid: str) -> List[ProductRecord]:
        return []

    def report_pending_assets(self, platform: str) -> List[ProductRecord]:
        return []

    def request_reprocess(self, source_uuid: str) -> Dict[str, Any]:
        return {
            "supported": False,
            "source_uuid": source_uuid,
            "message": "Local O3DE adapter does not request reprocess in this integration-gated slice.",
        }

    def clear_fingerprint(self, source_uuid: str) -> Dict[str, Any]:
        return {
            "supported": False,
            "source_uuid": source_uuid,
            "message": "Local O3DE adapter does not clear fingerprints in this integration-gated slice.",
        }

    def detect_environment(self) -> Dict[str, Any]:
        engine_root = str(self._env.get("O3DE_ENGINE_ROOT", "")).strip()
        project_root = str(self._env.get("O3DE_PROJECT_PATH", "")).strip()
        tools = self._find_tools()
        available = bool(engine_root and project_root and tools)
        messages: List[str] = []
        if not engine_root:
            messages.append("O3DE_ENGINE_ROOT is not set.")
        if not project_root:
            messages.append("O3DE_PROJECT_PATH is not set.")
        if not tools:
            messages.append("No O3DE query tooling was found on PATH.")
        if available:
            messages.append("O3DE tooling was detected, but live Asset System queries are not implemented in this slice.")
            available = False
        return {
            "available": available,
            "engine_root": engine_root,
            "project_root": project_root,
            "tools": tools,
            "messages": messages,
        }

    def resolve_manifest_products(
        self,
        manifest: Mapping[str, Any],
        *,
        platform: str = "pc",
        strict: bool = True,
        strict_integration: bool = False,
    ) -> AssetSystemResolverResult:
        detection = self.detect_environment()
        status = "fail" if strict_integration else "skipped"
        warnings = [] if strict_integration else [MXN_VALIDATION_TOOL_UNAVAILABLE]
        errors = [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict_integration else []
        messages = list(detection["messages"])
        messages.append(
            "Local O3DE integration is gated and unavailable; no Editor, Asset Processor, or live Asset System query ran."
        )
        return AssetSystemResolverResult(
            mode="unavailable",
            status=status,
            products=[],
            pending_assets=[],
            missing_expected_product_types=[],
            warnings=warnings,
            errors=errors,
            messages=messages,
            integration_executed=False,
            live_o3de_execution=False,
            cache_heuristic_used=False,
            evidence_refs=[
                {
                    "id": "local-o3de-integration-gate",
                    "kind": "integration_check",
                    "source": "LocalO3DEAssetSystemAdapter.detect_environment",
                }
            ],
        )

    def _find_tools(self) -> List[str]:
        found: List[str] = []
        for directory in self._path_entries:
            for tool_name in self.TOOL_NAMES:
                candidate = directory / tool_name
                if candidate.exists() and candidate.is_file():
                    found.append(normalize_path_text(str(candidate)))
        return sorted(set(found))


def coerce_product_records(records: Iterable[Any]) -> List[ProductRecord]:
    products: List[ProductRecord] = []
    for record in records:
        if isinstance(record, ProductRecord):
            products.append(record)
        elif isinstance(record, dict):
            products.append(ProductRecord.from_mapping(record))
        elif hasattr(record, "product_type") and hasattr(record, "product_path"):
            products.append(
                ProductRecord(
                    product_type=str(getattr(record, "product_type", "")),
                    product_path=str(getattr(record, "product_path", "")),
                    platform=str(getattr(record, "platform", "pc")),
                    status=str(getattr(record, "status", "ready")),
                    source_uuid=str(getattr(record, "source_uuid", "")),
                    asset_id=str(getattr(record, "asset_id", "")),
                    source_sub_id=str(getattr(record, "source_sub_id", "")),
                    relative_product_path=str(getattr(record, "relative_product_path", "")),
                    sha256=str(getattr(record, "sha256", "")),
                    sha256_available=bool(getattr(record, "sha256_available", False)),
                    produced_by_source_uuid=bool(getattr(record, "produced_by_source_uuid", True)),
                    evidence_source=str(getattr(record, "evidence_source", "fixture")),
                )
            )
    return products


def integration_gate_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    return str(env.get("MAXINE_ENABLE_O3DE_INTEGRATION", "")).strip() == "1"


def select_asset_system_adapter(
    *,
    enable_o3de_integration: bool = False,
    env: Mapping[str, str] | None = None,
) -> ProductResolver:
    if enable_o3de_integration or integration_gate_enabled(env):
        return LocalO3DEAssetSystemAdapter(env=env)
    return FixtureAssetSystemAdapter()


def resolve_manifest_products(
    manifest: Mapping[str, Any],
    *,
    enable_o3de_integration: bool = False,
    platform: str = "pc",
    strict: bool = True,
    strict_integration: bool = False,
    env: Mapping[str, str] | None = None,
) -> AssetSystemResolverResult:
    adapter = select_asset_system_adapter(enable_o3de_integration=enable_o3de_integration, env=env)
    return adapter.resolve_manifest_products(
        manifest,
        platform=platform,
        strict=strict,
        strict_integration=strict_integration,
    )


def _resolve_with_fixture_data(
    manifest: Mapping[str, Any],
    *,
    mode: str,
    platform: str,
    strict: bool,
) -> AssetSystemResolverResult:
    from tools.o3de.product_matrix_resolver import validate_expected_products

    job = manifest.get("job") if isinstance(manifest.get("job"), Mapping) else {}
    lane = str(job.get("lane", "")).strip()
    o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), Mapping) else {}
    product_resolution = o3de.get("product_resolution") if isinstance(o3de.get("product_resolution"), Mapping) else {}
    products = _manifest_product_records(manifest, platform=platform)
    cache_heuristic_used = bool(product_resolution.get("cache_heuristic_used", False)) or any(
        _is_cache_heuristic_product(product) for product in products
    )
    matrix_result = validate_expected_products(
        lane,
        products,
        strict=strict,
        publish_tier=str(product_resolution.get("publish_tier", "package")),
        physics_enabled=bool(product_resolution.get("physics_enabled", False)),
        materialized=bool(product_resolution.get("materialized", False)),
        collider_waiver=bool(product_resolution.get("collider_waiver", False)),
        material_waiver=bool(product_resolution.get("material_waiver", False)),
        external_motion_required=bool(product_resolution.get("motion_required", False)),
        cache_heuristic_used=cache_heuristic_used,
    )
    expected = [str(product_type).strip() for product_type in o3de.get("expected_product_types", [])]
    present = {product.product_type for product in products}
    pending = [
        PendingAssetRecord(
            source_uuid=product.source_uuid,
            platform=product.platform,
            status=product.status,
            reason=f"Product {product.product_type} is {product.status}.",
            evidence_source=product.evidence_source,
        )
        for product in products
        if product.status != "ready"
    ]
    source_reference = _manifest_source_reference(manifest)
    result_mode = "invalid" if lane in {"release_rigged", "external_rig_import"} and cache_heuristic_used else mode
    return AssetSystemResolverResult(
        mode=result_mode,
        status=matrix_result.status,
        products=products,
        pending_assets=pending,
        missing_expected_product_types=sorted(product_type for product_type in expected if product_type and product_type not in present),
        warnings=list(matrix_result.warning_codes),
        errors=list(matrix_result.error_codes),
        messages=list(matrix_result.messages),
        source_reference=source_reference,
        integration_executed=False,
        live_o3de_execution=False,
        cache_heuristic_used=cache_heuristic_used,
        evidence_refs=[
            {
                "id": f"{result_mode}-product-resolution",
                "kind": "product_resolution",
                "source": "manifest.o3de.actual_products",
            }
        ],
    )


def _manifest_product_records(manifest: Mapping[str, Any], *, platform: str) -> List[ProductRecord]:
    o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), Mapping) else {}
    product_resolution = o3de.get("product_resolution") if isinstance(o3de.get("product_resolution"), Mapping) else {}
    source_uuid = str(o3de.get("source_uuid", "")).strip()
    products = []
    for record in o3de.get("actual_products", []) if isinstance(o3de.get("actual_products"), list) else []:
        if isinstance(record, Mapping):
            payload = dict(record)
            payload.setdefault("platform", platform)
            payload.setdefault("source_uuid", source_uuid)
            payload.setdefault("evidence_source", str(product_resolution.get("adapter", "fixture")).strip() or "fixture")
            payload.setdefault("produced_by_source_uuid", bool(source_uuid))
            products.append(ProductRecord.from_mapping(payload))
    return products


def _manifest_source_reference(manifest: Mapping[str, Any]) -> SourceInfo | None:
    o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), Mapping) else {}
    inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), Mapping) else {}
    sources = inputs.get("sources", []) if isinstance(inputs.get("sources"), list) else []
    source_path = ""
    if sources and isinstance(sources[0], Mapping):
        source_path = normalize_path_text(str(sources[0].get("relative_path", sources[0].get("path", ""))).strip())
    source_uuid = str(o3de.get("source_uuid", "")).strip()
    if not source_uuid and not source_path:
        return None
    return SourceInfo(
        source_uuid=source_uuid,
        source_path=source_path,
        scan_folder="Assets",
        project_name=str(o3de.get("project_name", "")).strip(),
    )


def _is_cache_heuristic_product(product: ProductRecord) -> bool:
    evidence = product.evidence_source.strip().lower()
    if evidence in {"cache_heuristic", "newest_cache_file", "best_looking_cache_file", "fallback_mesh_selection"}:
        return True
    return product.produced_by_source_uuid is False and evidence not in {"fixture", "local_o3de", "asset_system"}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve MAXINE O3DE product records through fixture or gated local adapters.")
    parser.add_argument("--manifest", required=True, help="Manifest path to resolve.")
    parser.add_argument("--platform", default="pc", help="Target O3DE platform.")
    parser.add_argument("--enable-o3de-integration", action="store_true", help="Opt into local O3DE adapter detection.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail when local O3DE tooling is unavailable.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    path = Path(args.manifest)
    if not path.is_absolute():
        path = Path.cwd() / path
    result = resolve_manifest_products(
        _load_json(path),
        enable_o3de_integration=args.enable_o3de_integration,
        platform=args.platform,
        strict=True,
        strict_integration=args.strict_integration,
    )
    print(json.dumps(result.to_payload(), indent=2))
    if result.status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
