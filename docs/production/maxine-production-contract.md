# MAXINE Production Contract

This contract defines the static production-readiness foundation for the M.A.X.I.N.E. O3DE character pipeline. It is evidence infrastructure only: validators do not publish, spawn, contact external services, or run O3DE Editor or Asset Processor.

## Required Manifest Sections

Every job manifest includes:

- `schema_version`
- `job`
- `identity`
- `inputs`
- `generation`
- `dcc_conform`
- `o3de`
- `qc`
- `runtime_validation`
- `evidence`
- `provenance`
- `undo`
- `cleanup`

The supported production-readiness lanes are `draft_mesh`, `release_rigged`, and `external_rig_import`. Supported statuses are `pass`, `warn`, `fail`, and `pending_manual`.

## Publication Contract

Release success is package-first. A spawn or viewport-only check is not enough for release publication. A release package records source asset references, product asset records, a prefab/procprefab reference, the manifest, QC report, evidence bundle, undo plan, and cleanup plan.

Draft packages may pass with `azmodel` plus smoke evidence. Release packages require explicit product records and a prefab/procprefab reference. Cache newest-file guessing is forbidden for release decisions.

## Undo And Cleanup

Undo and cleanup are required even for fixture validation. Current validators only verify plan presence and never perform destructive cleanup. Future execution runners must keep cleanup path-scoped and must prove no production, engine, or Cache writes unless separately admitted.

## Local Validation

Run the safe static suite without O3DE or network access:

```powershell
python tools/validation/validate_all.py
```

Run strict QC against the release fixture:

```powershell
python tools/qc/run_qc.py --manifest examples/manifests/release_rigged.pass.example.json --strict
```

Integration checks for O3DE Editor, Asset Processor Batch, Blender, Mixamo/Adobe, and model downloads are intentionally skipped unless a future integration job explicitly enables them.

For local O3DE adapter detection, use:

```powershell
python tools/validation/validate_all.py --enable-o3de-integration
```

The default resolver remains deterministic fixture mode. Release lanes still fail if product resolution relies on cache guessing rather than source UUID or trusted product metadata.

Run the Asset Processor Batch golden corpus fixture proof with:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --mode fixture
```

Optional local Asset Processor Batch detection is gated:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch
```

Run the Editor Python package/prefab smoke fixture bridge with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
```

Optional local Editor detection is gated:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke
```

Fixture Editor smoke reports connect package/prefab/procprefab refs to product resolver evidence, Asset Processor Batch proof, source UUID identity, and expected entity/component structure. They must keep `live_editor_execution=false` unless a future admitted integration job actually runs Editor Python.

Run the private-runner readiness and suite wrappers with:

```powershell
python tools/ci/o3de_runner_readiness.py
python tools/ci/run_o3de_integration_suite.py --dry-run
python tools/ci/run_o3de_integration_suite.py --mode fixture
```

The private Windows workflow is manual-only and targets `[self-hosted, Windows, X64, o3de, maxine-private]`. It does not register runners, require secrets, run on push/pull_request, publish, or make live O3DE checks part of normal CI.
