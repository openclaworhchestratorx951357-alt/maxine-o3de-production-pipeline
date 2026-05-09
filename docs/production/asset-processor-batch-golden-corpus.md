# Asset Processor Batch Golden Corpus Proof

This proof layer connects the manifest, product resolver, and product matrix contracts to a small JSON-only Asset Processor Batch corpus.

Default fixture validation:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --mode fixture
```

The fixture corpus validates expected products, produced product records, pending assets, missing products, source UUID identity, and release cache-heuristic rejection. It does not run O3DE, Asset Processor Batch, Editor, publication, network calls, or external services.

Optional local Asset Processor Batch detection:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch
```

Strict local detection:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --strict-integration
```

When local tooling is unavailable, non-strict mode reports `skipped` with `MXN_VALIDATION_TOOL_UNAVAILABLE`. Strict mode fails with the same code. Skipped integration is not a pass.

`live_asset_processor_batch_execution` remains false unless a future explicitly gated command actually runs Asset Processor Batch and parses its evidence. This proof does not prove live Editor/runtime smoke.
