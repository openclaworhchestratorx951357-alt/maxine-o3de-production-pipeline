# Controlled Real MAX_BIPED Skeleton Evidence v1

## Summary

This slice integrates bounded controlled-real MAX_BIPED skeleton evidence for pilot candidates while preserving an execution-blocked posture.

`max_biped_v1_skeleton_contract` remains evidence-only:

- no Blender/DCC execution
- no O3DE execution
- no Asset Processor execution
- no spawn/publish
- no Cache/live DB access

## Inputs and Scope

Controlled-real pilot fixture:

- `examples/sandbox/max-biped-skeleton-evidence/pilot-candidates/max_biped_v1_skeleton_controlled_real.fixture.json`

Runner integration:

- `tools/release-lane/run_pilot_release_chain_validation.py`

Validator:

- `tools/max-biped-skeleton/validate_max_biped_skeleton_evidence_report.py`

Schema:

- `schemas/maxine_max_biped_skeleton_evidence_report.schema.json`

## Evidence Contract Highlights

The report requires explicit controlled-real skeleton evidence metadata:

- candidate identity/reference (`candidate_id`, `source_asset_reference`, `source_evidence_ref`)
- skeleton profile metadata (`skeleton_profile_id`, `skeleton_profile_version`)
- contract dimension statuses (root/pelvis/spine/neck-arm-leg chains, hand/finger, naming, hierarchy, orientation, scale, bind pose)
- structural coverage (`bone_count`, `required_bones_present`, `missing_required_bones`, `extra_bones`)
- readiness statuses (`retarget_readiness_status`, `animation_smoke_dependency_status`)
- evidence class (`fixture|imported|controlled_real`)
- claim status (`evidence_only|not_authoritative`)
- blocked safety statuses (`dcc_execution_status`, `blender_execution_status`, `o3de_execution_status`, `production_write_status`)

## Proof-Flow Effect

- The pilot runner validates controlled-real MAX_BIPED skeleton evidence for `max_biped_v1_skeleton_contract`.
- Release-lane evidence admission status recognizes `max_biped_v1_skeleton_contract` as controlled-real evidence.
- Execution remains unadmitted and blocked.

## Non-Admissions Preserved

- no broad O3DE execution
- no broad/real Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID claims
- no authoritative Asset ID claims
- no authoritative Product ID claims
- no production path writes
- no engine path writes
