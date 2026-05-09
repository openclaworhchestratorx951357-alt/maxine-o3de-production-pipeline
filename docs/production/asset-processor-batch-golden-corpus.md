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

## APB-Only Live Path

The first live path is APB-only. It still does not run Editor, Editor Python, prefab smoke, release packaging, or publication.

Readiness only:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness
```

Non-strict APB live attempt:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
```

Strict APB live attempt:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

Live APB requires all gates:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\MAXINE_GoldenCorpus"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
```

`O3DE_PROJECT_PATH\project.json` must match the golden fixture project name. If any gate, tool, or project path is missing, non-strict mode reports skipped/unavailable and strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE`.

When APB actually executes, stdout/stderr and the APB live report are written under `artifacts/o3de-integration/apb/`, which is gitignored. `live_asset_processor_batch_execution` is true only after a command actually runs. `live_editor_execution` and live publication remain false.

Live APB success is not production publication and is not Editor/runtime smoke.
