# DCC Conform v1 (Evidence-Only)

## What This Slice Does

`dcc_conform_v1` defines a contract-first, non-destructive DCC conform evidence report for pilot release-lane candidates.

- validates normalized DCC conform report JSON
- preserves `MAX_BIPED_v1` target enforcement
- emits manifest-attachable QC output
- supports `pass`, `warn`, `fail`, and `pending_manual`
- supports bounded controlled-real evidence metadata without admitting execution

## What This Slice Does Not Do

- does not execute Blender/DCC
- does not execute O3DE
- does not execute Asset Processor
- does not spawn or publish
- does not read Cache or live asset DB
- does not make authoritative source UUID / Asset ID / Product ID claims

## Report Contract

Schema:

- `schemas/maxine_dcc_conform_report.schema.json`

Required controlled-real evidence fields:

- `candidate_id`
- `source_asset_reference`
- `source_evidence_ref`
- `dcc_tool_name`
- `dcc_tool_version`
- `conform_profile_id`
- `conform_profile_version`
- `unit_scale_status`
- `orientation_status`
- `origin_status`
- `transform_freeze_status`
- `mesh_naming_status`
- `material_slot_naming_status`
- `skeleton_reference_status`
- `export_format_status`
- `required_axes`
- `required_units`
- `evidence_class`: `fixture | imported | controlled_real`
- `claim_status`: `evidence_only | not_authoritative`
- `safety` with blocked statuses:
  - `dcc_execution_status`
  - `blender_execution_status`
  - `production_write_status`

Existing report sections remain required:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source metadata: `source.*`
- target metadata: `target.*`
- DCC metadata: `dcc.*`
- transform metadata: `transform.*`
- skeleton metadata: `skeleton.*`
- findings array
- manifest attachment payload

## Manifest Integration

Current attachment path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

DCC conform check id:

- `dcc_conform_v1`

## Validator

Validator script:

- `tools/dcc-conform/validate_dcc_conform_report.py`

Behavior:

- exits `0` for `pass`
- exits `0` for `warn` only when `--allow-warn` is supplied
- exits nonzero for `fail`
- exits nonzero for `warn` without `--allow-warn`

## Controlled Real Evidence Fixture

Pilot controlled-real fixture path:

- `examples/sandbox/dcc-conform-evidence/pilot-candidates/max_biped_v1_dcc_conform_controlled_real.fixture.json`

The pilot runner now validates this bounded fixture for `dcc_conform_v1` and keeps execution blocked.

## Safety Boundaries

This slice is evidence/report-validation only and preserves:

- no broad execution admissions
- no Blender/DCC execution admission
- no spawn/publish admission
- no Cache/live DB admission
- no authoritative ID claims
- no production/engine path writes
