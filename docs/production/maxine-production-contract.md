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
