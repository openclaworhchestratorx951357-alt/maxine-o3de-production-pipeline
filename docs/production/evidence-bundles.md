# Evidence Bundles

An evidence bundle is the reviewable index of files that support a manifest and QC report. It records IDs, kinds, paths, and hashes when known.

Evidence bundles in this slice are static and local. They must not claim live O3DE runtime success, Asset Processor success, or external service success unless those systems actually ran under a future admitted integration job.

The example bundle is:

```text
examples/production/evidence_bundle.release_rigged.pass.example.json
```

Strict manifest validation requires referenced evidence files to exist.

## Product Resolver Evidence

Evidence bundles and manifests should record the resolver result when product records are used:

- `resolver_mode`: `fixture`, `local_o3de`, `unavailable`, or `invalid`
- `integration_executed`: true only when the gated adapter actually performed a local query
- `live_o3de_execution`: true only when local O3DE tooling actually ran
- `fixture_data_used`: true for deterministic fixture validation
- `cache_heuristic_used`: true if any product evidence came from cache guessing
- `evidence_refs`: local evidence records that explain where the resolver data came from

Fixture examples set `integration_executed` and `live_o3de_execution` to false. Optional O3DE integration checks that are skipped must remain marked skipped or unavailable, not pass.

## Asset Processor Batch Proof Evidence

Asset Processor Batch proof evidence may be attached as:

- APB fixture report path, such as `examples/golden-corpus/release_rigged/asset_processor_batch.fixture.json`
- stdout/stderr refs only when a future gated APB command actually runs
- `integration_enabled`
- `live_asset_processor_batch_execution`
- skipped reason and error code when tooling is unavailable
- product resolver/product matrix refs used to classify products

Fixture reports must not claim real AP logs or live execution.

## Editor Smoke Evidence

Editor Python package/prefab smoke evidence may be attached as:

- Editor smoke fixture report path, such as `examples/editor-smoke/release_rigged.fixture.report.json`
- stdout/stderr/editor log refs only when a future gated Editor command actually runs
- `integration_enabled`
- `live_editor_execution`
- skipped reason and error code when tooling is unavailable
- product resolver and Asset Processor Batch proof refs used to connect instantiation evidence to source/product identity
- screenshot refs only when fixture-labeled or actually captured

Fixture reports must not claim real Editor logs, screenshots, level mutation, or live Editor execution.
