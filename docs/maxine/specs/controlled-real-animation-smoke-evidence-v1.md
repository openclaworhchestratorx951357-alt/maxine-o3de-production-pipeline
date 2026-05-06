# Controlled Real Animation Smoke Evidence v1

## Summary

This slice integrates bounded controlled-real animation smoke evidence for pilot candidates while preserving an execution-blocked posture.

`animation_smoke_v1` remains evidence-only:

- no Blender/DCC execution
- no O3DE execution
- no Asset Processor execution
- no runtime playback execution
- no spawn/publish
- no Cache/live DB access

## Inputs and Scope

Controlled-real pilot fixture:

- `examples/sandbox/animation-smoke-evidence/pilot-candidates/max_biped_v1_animation_smoke_controlled_real.fixture.json`

Runner integration:

- `tools/release-lane/run_pilot_release_chain_validation.py`

Validator:

- `tools/animation-smoke/validate_animation_smoke_report.py`

Schema:

- `schemas/maxine_animation_smoke_report.schema.json`

## Evidence Contract Highlights

The report requires explicit controlled-real animation smoke evidence metadata:

- candidate identity/reference (`candidate_id`, `source_asset_reference`, `source_evidence_ref`)
- profile metadata (`animation_profile_id`, `animation_profile_version`)
- actor/motion references (`actor_asset_reference`, `motion_asset_reference`, optional motion-set/anim-graph references)
- skeleton linkage (`skeleton_profile_id=MAX_BIPED_v1`, `skeleton_compatibility_status`, `bind_pose_compatibility_status`)
- clip/smoke statuses (`clip_count`, `smoke_clip_names`, `clip_duration_status`, `missing_clip_status`, `retarget_readiness_status`, `frame_range_status`, `animation_budget_status`, optional loopability/motion-event statuses)
- evidence class (`fixture|imported|controlled_real`)
- claim status (`evidence_only|not_authoritative`)
- blocked safety statuses (`dcc_execution_status`, `blender_execution_status`, `o3de_execution_status`, `asset_processor_execution_status`, `runtime_playback_status`, `production_write_status`)

## Proof-Flow Effect

- The pilot runner validates controlled-real animation smoke evidence for `animation_smoke_v1`.
- Release-lane evidence admission status now recognizes `animation_smoke_v1` as controlled-real evidence.
- Execution remains unadmitted and blocked.

## Non-Admissions Preserved

- no broad O3DE execution
- no broad/real Asset Processor execution
- no Blender/DCC execution
- no runtime playback execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID claims
- no authoritative Asset ID claims
- no authoritative Product ID claims
- no production path writes
- no engine path writes
