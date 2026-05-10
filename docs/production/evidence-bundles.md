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

When APB live execution is explicitly admitted on a private runner, APB evidence may include:

- `golden_project_fixture_ref`
- `integration_executed`
- `live_asset_processor_batch_execution`
- safe command argv
- exit code and duration
- stdout/stderr refs under `artifacts/o3de-integration/apb/`
- APB live report ref
- `live_editor_execution=false`
- `live_publication=false`

Generated live APB logs are not fixture reports and are not committed by default.

Release-rigged APB evidence can also include a source capability audit:

```powershell
python tools/o3de/audit_golden_corpus_sources.py --corpus examples/golden-corpus --project $env:O3DE_PROJECT_PATH --json
```

The audit records whether controlled sources exist for actor, motion, motionset, animgraph, and pxmesh scene settings. It does not replace Asset Processor product evidence. If APB exits `0` but the database lacks `.pxmesh`, `actor`, `motion`, `motionset`, or `animgraph`, the evidence bundle remains failed until the product is produced or an explicit policy waiver is added and validated.

For product-specific live APB evidence, use the APB product evidence audit:

```powershell
python tools/o3de/audit_apb_product_evidence.py --project $env:O3DE_PROJECT_PATH --apb-report <asset_processor_batch_live_report.json> --apb-executable $env:ASSET_PROCESSOR_BATCH_EXECUTABLE --json
```

The audit verifies `.pxmesh` through APB report or Asset Processor database evidence tied to the controlled release source. It may list filename-like or physics-like products for diagnostics, but those diagnostic matches do not satisfy release proof.

As of the pxmesh resolution follow-up, `.pxmesh` is present for the controlled release source and the product matrix evidence is satisfied. The APB-only suite still fails closed because APB exits nonzero on an unrelated engine/Gem pass asset; that is recorded separately as `MXN_APB_PROCESS_EXIT_NONZERO`.

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

## Golden Project Fixture Evidence

Golden project fixture evidence may be attached as:

- project fixture path, such as `examples/o3de-golden-project/maxine-golden-project.fixture.json`
- local readiness report when the private runner inspected env vars/tool paths
- `live_o3de_execution`, `live_asset_processor_batch_execution`, and `live_editor_execution`
- temp-level policy refs under `Levels/_maxine_smoke`
- evidence/artifact retention roots under `Saved/MaxineEvidence`, `Saved/Logs/Maxine`, and `Saved/Screenshots/Maxine`
- skipped reason and `MXN_VALIDATION_TOOL_UNAVAILABLE` when local project/tooling paths are unavailable

Fixture and skipped readiness reports must not claim project mutation, APB execution, Editor execution, screenshots, or logs that were not actually produced.
