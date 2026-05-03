# QC Gates

Publication is blocked unless required gates pass or receive an approved warning policy outcome.

## Publication Gates

- input integrity
- scan-safe packaging
- Asset Processor completion
- scale/origin/facing
- geometry sanity
- UV/material sanity
- skeleton contract
- skinning quality
- facial capability
- collision legality
- animation sanity
- runtime smoke
- cleanup and undo
- provenance completeness

| Check | Pass criteria | Failure class | Evidence required |
|---|---|---|---|
| Input integrity | Inputs exist, hashable, and match declared format | `input_missing` / `input_mismatch` | Input inventory, checksums, intake log |
| Scan-safe packaging | Draft package structure conforms to expected lane contract | `package_contract_violation` | Package tree snapshot, manifest diff |
| Asset Processor completion | Required products are generated for declared lane | `product_missing` | AP logs, product index, resolver output |
| Scale/origin/facing | Scale units, pivot, and facing direction within policy | `transform_policy_fail` | Measurement report, viewport screenshot |
| Geometry sanity | Polycount, non-manifold checks, and degenerates within thresholds | `geometry_invalid` | Mesh stats, validator log |
| UV/material sanity | UVs non-empty and materials resolvable | `uv_material_invalid` | UV preview, material assignment report |
| Skeleton contract | Bone hierarchy meets required rig profile | `skeleton_contract_fail` | Skeleton map, rig validation report |
| Skinning quality | Weights normalized and no major envelope artifacts | `skinning_quality_fail` | Weight diagnostics, pose screenshots |
| Facial capability | Facial rig/morph set meets lane minimums | `facial_capability_fail` | Facial feature matrix, test captures |
| Collision legality | Collision setup matches gameplay/legal policy | `collision_policy_fail` | Collider manifest, physics validation log |
| Animation sanity | Motions import, retarget, and play without hard errors | `animation_sanity_fail` | Motion import log, playback capture |
| Runtime smoke | Editor automation smoke succeeds in target level | `runtime_smoke_fail` | Script logs, screenshots, console output |
| Cleanup and undo | Temporary artifacts cleaned and rollback path verified | `cleanup_undo_fail` | Cleanup log, undo transaction proof |
| Provenance completeness | Manifest provenance section complete and traceable | `provenance_incomplete` | Manifest provenance block, source references |
