# Controlled Real DCC Conform Evidence v1

## Summary

This slice integrates bounded controlled-real DCC conform evidence for pilot candidates while preserving an execution-blocked posture.

`dcc_conform_v1` remains evidence-only:

- no Blender/DCC execution
- no O3DE execution
- no Asset Processor execution
- no spawn/publish
- no Cache/live DB access

## Inputs and Scope

Controlled-real pilot fixture:

- `examples/sandbox/dcc-conform-evidence/pilot-candidates/max_biped_v1_dcc_conform_controlled_real.fixture.json`

Runner integration:

- `tools/release-lane/run_pilot_release_chain_validation.py`

Validator:

- `tools/dcc-conform/validate_dcc_conform_report.py`

Schema:

- `schemas/maxine_dcc_conform_report.schema.json`

## Evidence Contract Highlights

The report now requires explicit controlled-real evidence metadata:

- candidate identity/reference (`candidate_id`, `source_asset_reference`, `source_evidence_ref`)
- DCC/profile metadata (`dcc_tool_name`, `dcc_tool_version`, `conform_profile_id`, `conform_profile_version`)
- conform outcome statuses per required dimension (unit scale, orientation, origin, freeze, naming, skeleton reference, export format)
- required axes/units declarations
- evidence class (`fixture|imported|controlled_real`)
- claim status (`evidence_only|not_authoritative`)
- blocked safety statuses (`dcc_execution_status`, `blender_execution_status`, `production_write_status`)

## Proof-Flow Effect

- The pilot runner validates controlled-real DCC conform evidence for `dcc_conform_v1`.
- Release-lane evidence admission status now recognizes `dcc_conform_v1` as controlled-real evidence.
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
