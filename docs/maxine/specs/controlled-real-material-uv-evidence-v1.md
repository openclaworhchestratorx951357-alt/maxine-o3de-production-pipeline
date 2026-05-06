# Controlled Real Material/UV Evidence v1

## Summary

This slice integrates bounded controlled-real material/UV evidence for pilot candidates while preserving an execution-blocked posture.

`material_uv_qc_v1` remains evidence-only:

- no Blender/DCC execution
- no O3DE execution
- no Asset Processor execution
- no spawn/publish
- no Cache/live DB access

## Inputs and Scope

Controlled-real pilot fixture:

- `examples/sandbox/material-uv-evidence/pilot-candidates/max_biped_v1_material_uv_controlled_real.fixture.json`

Runner integration:

- `tools/release-lane/run_pilot_release_chain_validation.py`

Validator:

- `tools/material-uv-qc/validate_material_uv_qc_report.py`

Schema:

- `schemas/maxine_material_uv_qc_report.schema.json`

## Evidence Contract Highlights

The report requires explicit controlled-real material/UV evidence metadata:

- candidate identity/reference (`candidate_id`, `source_asset_reference`, `source_evidence_ref`)
- profile metadata (`material_uv_profile_id`, `material_uv_profile_version`)
- policy dimension statuses:
  - `material_slot_status`
  - `material_naming_status`
  - `standard_pbr_status`
  - `texture_reference_status`
  - `missing_texture_status`
  - `texture_resolution_status`
  - `texture_count_status`
  - `required_uv_sets_present`
  - `uv_overlap_status`
  - `uv_out_of_bounds_status`
  - `texel_density_status`
  - `lightmap_uv_status`
  - `material_budget_status`
  - `texture_budget_status`
- structural counts (`material_slot_count`, `uv_set_count`)
- evidence class (`fixture|imported|controlled_real`)
- claim status (`evidence_only|not_authoritative`)
- blocked safety statuses (`dcc_execution_status`, `blender_execution_status`, `o3de_execution_status`, `asset_processor_execution_status`, `production_write_status`)

## Proof-Flow Effect

- The pilot runner validates controlled-real material/UV evidence for `material_uv_qc_v1`.
- Release-lane evidence admission status now recognizes `material_uv_qc_v1` as controlled-real evidence.
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
