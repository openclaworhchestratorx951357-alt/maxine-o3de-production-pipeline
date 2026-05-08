"""Asset System product-resolution adapter contracts and fixture implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Protocol

from tools.validation.maxine_paths import normalize_path_text


@dataclass(frozen=True)
class ProductRecord:
    product_type: str
    product_path: str
    platform: str = "pc"
    status: str = "ready"
    source_uuid: str = ""
    asset_id: str = ""

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "ProductRecord":
        return cls(
            product_type=str(payload.get("product_type", "")).strip(),
            product_path=normalize_path_text(str(payload.get("product_path", payload.get("path", ""))).strip()),
            platform=str(payload.get("platform", "pc")).strip() or "pc",
            status=str(payload.get("status", "ready")).strip() or "ready",
            source_uuid=str(payload.get("source_uuid", "")).strip(),
            asset_id=str(payload.get("asset_id", "")).strip(),
        )


@dataclass(frozen=True)
class SourceInfo:
    source_uuid: str
    source_path: str
    scan_folder: str = "Assets"


class ProductResolver(Protocol):
    def generate_relative_source_path(self, source_path: str) -> str: ...

    def list_asset_safe_folders(self) -> List[str]: ...

    def get_source_info_by_source_path(self, source_path: str) -> SourceInfo | None: ...

    def get_source_info_by_source_uuid(self, source_uuid: str) -> SourceInfo | None: ...

    def list_products_by_source_uuid(self, source_uuid: str) -> List[ProductRecord]: ...

    def report_pending_assets(self, platform: str) -> List[ProductRecord]: ...

    def request_reprocess(self, source_uuid: str) -> Dict[str, Any]: ...

    def clear_fingerprint(self, source_uuid: str) -> Dict[str, Any]: ...


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


def coerce_product_records(records: Iterable[Any]) -> List[ProductRecord]:
    products: List[ProductRecord] = []
    for record in records:
        if isinstance(record, ProductRecord):
            products.append(record)
        elif isinstance(record, dict):
            products.append(ProductRecord.from_mapping(record))
    return products
