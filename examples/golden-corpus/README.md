# Asset Processor Batch Golden Corpus

This corpus is a deterministic, JSON-only proof layer for Asset Processor Batch product expectations.

Default validation uses fixture reports and does not require O3DE:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --mode fixture
```

Optional local detection is explicit and reports skipped when tooling is unavailable:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --strict-integration
```

The APB-only private-runner path must be tied to the golden project fixture:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
```

Without all live APB gates and local O3DE/APB paths, that command reports skipped/unavailable in non-strict mode. It does not run Editor or publication.

The corpus intentionally includes pass and fail fixtures. The fixture harness passes when each case's observed validation status matches its expected report status.
