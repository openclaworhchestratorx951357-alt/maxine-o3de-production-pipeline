# Material/UV QC v1 (Evidence-Only)

## What This Slice Does

`Material/UV QC v1` defines an evidence-only validation contract for release-lane material and UV readiness reports.

- validates structured Material/UV QC report JSON
- checks required UV-set presence and missing set reporting
- checks material slot budgets with explicit severity policy
- checks missing required materials/textures
- checks oversized texture reporting against configured texture budget
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute Blender
- does not execute O3DE
- does not execute Asset Processor
- does not inspect real DCC binaries or asset processors
- does not mutate source art assets
- does not spawn or publish
- does not read Cache or live asset databases

## Report Contract

Schema:

- `schemas/maxine_material_uv_qc_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source_path`, `source_kind`, optional `sha256`
- target profile: `package_tier`, `material_profile`
- material summary:
  - `material_slot_count`
  - `material_slot_budget`
  - `slot_budget_exceeded_severity`
  - `missing_materials`
  - `unsupported_materials`
  - `texture_references`
  - `missing_textures`
- UV summary:
  - `required_uv_sets`
  - `present_uv_sets`
  - `missing_uv_sets`
  - `overlapping_uvs_status`
  - `out_of_bounds_uvs_status`
- texture budget:
  - `max_texture_resolution`
  - `oversized_textures`
  - `oversized_textures_severity`
  - `texture_count`
- structured findings
- manifest attachment payload

## Material Budget Logic

- If `material_slot_count > material_slot_budget`, the validator emits a finding using `slot_budget_exceeded_severity`.
- This keeps warn-vs-fail behavior explicit and deterministic in the report contract.

## UV Requirement Logic

- Required UV sets are computed from `required_uv_sets - present_uv_sets`.
- Any missing required UV sets produce a fail-level finding.
- `missing_uv_sets` is checked against computed values to catch reporting mismatches.

## Texture-Reference Evidence

- `texture_references` provide evidence of material-to-texture linkage.
- `missing_textures` trigger fail-level findings.
- `oversized_textures` are evaluated against `max_texture_resolution` and severity policy.

## Manifest v1 Integration

Current attachment path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `material_uv_qc_v1`

## Validator

Validator script:

- `tools/material-uv-qc/validate_material_uv_qc_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `warn` without `--allow-warn`
- exits nonzero on `fail`

## Safety Boundaries

This slice is report-validation-only and preserves blocked/unadmitted surfaces:

- no Blender execution
- no O3DE execution
- no real Asset Processor execution
- no spawn/publish
- no Cache/live DB access
- no source/product UUID claims
- no new generation lanes
- no destructive cleanup

## Future Path (Not Implemented Here)

A future bounded slice may add real DCC extraction steps and evidence capture from controlled tooling. That execution path is not implemented in this slice.
