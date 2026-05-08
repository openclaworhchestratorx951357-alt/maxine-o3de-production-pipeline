# Asset System Adapter

The production-readiness layer uses `tools/o3de/product_resolver.py` as the adapter boundary for O3DE Asset System product resolution.

The adapter contract covers:

- relative source path generation
- asset-safe folder listing
- source lookup by source path or source UUID
- product listing by source UUID
- pending product reporting by platform
- explicit reprocess or fingerprint-clear requests where a future real integration supports them
- product classification against the expected product matrix

The current implementation includes a deterministic fixture resolver only. It does not read live Cache files, Asset Processor databases, or O3DE services. A future real adapter should preserve the same interface and remain read-only until separately admitted.
