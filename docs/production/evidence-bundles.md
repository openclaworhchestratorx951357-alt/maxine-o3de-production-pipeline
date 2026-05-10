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

As of the pxmesh resolution follow-up, `.pxmesh` is present for the controlled release source and the product matrix evidence is satisfied.

The follow-up DiffuseProbeGrid slice fixed the separate `MXN_APB_PROCESS_EXIT_NONZERO` condition by removing unnecessary `DiffuseProbeGrid` enablement from the controlled project and regenerating project-specific registry metadata. The clean APB-only evidence is represented by:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.apb-clean.pass.example.json
```

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

Readiness-only Editor smoke evidence may be committed when it is sanitized and clearly unavailable/skipped or when it records a produced paired Editor executable without launching Editor. It can record the paired Editor executable status, `EditorPythonBindings` status, temp-level policy, APB baseline reference, and closed publication/release-packaging gates.

The unavailable readiness example is:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.unavailable.example.json
```

The produced-Editor readiness example is:

```text
examples/editor-smoke/editor-smoke-readiness.release-rigged.editor-produced.example.json
```

Live Editor smoke evidence may be committed only when it is sanitized and clearly labels the outcome. The first live attempt is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```

That evidence records `live_editor_execution=true` because the Editor process actually launched, `status=stalled` because the wrapper timeout stopped the process, and closed safety gates:

- `live_publication=false`
- `release_packaging=false`
- `production_level_mutation=false`
- `live_asset_processor_batch_execution=false` for the Editor command itself

Live Editor evidence should also reference the APB baseline report that supplied complete product evidence. It must not duplicate APB report schema concepts beyond a compact product evidence summary and APB baseline ref.

`live_editor_execution=true` is allowed only when the Editor process actually ran. Missing Editor executables, build timeouts, failed readiness, nonzero Editor exits, and stalled Editor commands remain blockers, not passes.

The temp-level stall diagnostic adds a progress log reference to live Editor evidence:

- `progress_log_ref`: JSONL progress markers written beside the live report
- `last_progress_marker`: the final script-side marker used to classify a stall
- `stall_phase`: wrapper classification such as `runpython_not_invoked`, `azlmbr_import_stall`, `product_evidence_stall`, `temp_level_create_stall`, `idle_wait_stall`, `entity_create_stall`, or `report_write_stall`
- `diagnostic_mode`: `hello`, `product-evidence`, `temp-level`, `entity-minimal`, or `full`
- `process_tree_cleanup`: timeout cleanup status when a process tree must be stopped

The PR #116 stall was diagnosed as `idle_wait_stall`. The fixed full live smoke pass is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```

That pass evidence records `live_editor_execution=true`, `live_publication=false`, `release_packaging=false`, `production_level_mutation=false`, `cache_heuristic_used=false`, and entity/component smoke pass. Prefab and actor smoke remain explicitly `unavailable` until their Editor binding surfaces are pinned; they are not silently treated as pass.

## Golden Project Fixture Evidence

Golden project fixture evidence may be attached as:

- project fixture path, such as `examples/o3de-golden-project/maxine-golden-project.fixture.json`
- local readiness report when the private runner inspected env vars/tool paths
- `live_o3de_execution`, `live_asset_processor_batch_execution`, and `live_editor_execution`
- temp-level policy refs under `Levels/_maxine_smoke`
- evidence/artifact retention roots under `Saved/MaxineEvidence`, `Saved/Logs/Maxine`, and `Saved/Screenshots/Maxine`
- skipped reason and `MXN_VALIDATION_TOOL_UNAVAILABLE` when local project/tooling paths are unavailable

Fixture and skipped readiness reports must not claim project mutation, APB execution, Editor execution, screenshots, or logs that were not actually produced.
