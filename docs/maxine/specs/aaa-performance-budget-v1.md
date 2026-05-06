# AAA Performance Budget v1

`aaa_performance_budget_v1` defines an evidence-only, non-executing performance budget contract for pilot release-lane candidates.

## Contract

- report type: `AAA_PERFORMANCE_BUDGET_v1_REPORT`
- check id: `aaa_performance_budget_v1`
- contract id: `AAA_PERFORMANCE_BUDGET_v1`
- current attachment target: `qc.gates[]`
- future attachment target: `qc.checks[]`

## Required Core Fields

- `candidate_id`
- `source_asset_reference`
- `source_evidence_ref`
- `performance_profile_id=AAA_PERFORMANCE_BUDGET_v1`
- `performance_profile_version`
- `asset_tier`: `hero|npc|prop|environment`
- `evidence_class`: `fixture|imported|controlled_real`
- `triangle_count`
- `material_slot_count`
- `texture_count`
- `texture_resolution_max`
- `texture_memory_estimate_mb`
- `uv_set_count`
- `bone_count`
- `skin_influence_max`
- `lod_count`
- `animation_clip_count`
- `package_size_estimate_mb`
- budget status fields (`*_budget_status`)
- `runtime_load_readiness_status`
- `review_tier_status`
- `claim_status`: `evidence_only|not_authoritative`
- `safety` blocked fields

## Starting Budget Policy

Hero defaults:
- triangles: warn `>120000`, fail `>180000` unless explicitly waived
- material slots: warn `>6`, fail `>8` unless explicitly waived
- max texture resolution: warn `>4096`, fail `>8192` unless explicitly waived
- bones: warn `>160`, fail `>220` unless explicitly waived
- skin influences: warn `>4`, fail `>8`
- LOD count: warn `<4`

NPC defaults:
- triangles: warn `>60000`, fail `>100000` unless explicitly waived
- material slots: warn `>4`, fail `>6` unless explicitly waived
- max texture resolution: warn `>2048`, fail `>4096` unless explicitly waived
- bones: warn `>120`, fail `>180` unless explicitly waived
- skin influences: warn `>4`, fail `>8`
- LOD count: warn `<3`

## Waiver Rules

- waivers are explicit only: `waiver_status=waived` requires `waiver_ids` and `waiver_reasons`
- waived fail-threshold exceedances remain visible as warning findings
- waivers do not silently produce pass

## Safety Posture

- no O3DE/editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims

`aaa_performance_budget_v1` remains evidence-only and non-authoritative in this slice.
