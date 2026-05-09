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

## Resolver Modes

- `fixture`: the default resolver mode for CI and local validation. It reads manifest fixture records only, runs offline, and never requires O3DE, Asset Processor, Editor, credentials, or network access.
- `local_o3de`: reserved for a future read/query implementation that can resolve products from trusted local Asset System metadata by source UUID. It must stay behind an explicit gate.
- `unavailable`: the local O3DE gate was enabled, but required tooling or a safe query path was not available. Non-strict validation reports this as skipped. Strict integration validation fails with `MXN_VALIDATION_TOOL_UNAVAILABLE`.
- `invalid`: reserved for resolver states that cannot be trusted, including release attempts that depend only on cache guessing.

Default validation uses fixture mode:

```powershell
python tools/validation/validate_all.py
```

Optional local O3DE detection is explicit:

```powershell
python tools/validation/validate_all.py --enable-o3de-integration
python tools/o3de/product_resolver.py --manifest examples/manifests/release_rigged.pass.example.json --enable-o3de-integration
```

Strict integration mode treats missing local O3DE tooling as a failure:

```powershell
python tools/validation/validate_all.py --enable-o3de-integration --strict-integration
```

The environment variable gate is also supported:

```powershell
$env:MAXINE_ENABLE_O3DE_INTEGRATION='1'
python tools/validation/validate_all.py
```

This slice detects local tooling and records skipped/unavailable integration status. It does not run Editor, Asset Processor, publish, mutate project settings, or fake product metadata.

The Asset Processor Batch golden corpus proof builds on this adapter contract with JSON fixtures:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --mode fixture
```

## Resolver Evidence

Resolver evidence records:

- `resolver_mode`
- `status`
- `integration_executed`
- `live_o3de_execution`
- `fixture_data_used`
- `cache_heuristic_used`
- `evidence_refs`

`live_o3de_execution` may only be true after a future explicitly gated job actually runs local O3DE tooling.
