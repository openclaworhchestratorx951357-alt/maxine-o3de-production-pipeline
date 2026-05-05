# DCC Conform v1 (Evidence-Only)

## What This Slice Does

`DCC conform v1` defines a contract-first, non-destructive evidence report for release-lane character conform checks.

- validates normalized DCC conform report JSON
- enforces `MAX_BIPED_v1` targeting
- emits manifest-attachable QC output
- supports `pass`, `warn`, `fail`, and `pending_manual` outcomes

## What This Slice Does Not Do Yet

- does not execute Blender
- does not execute O3DE
- does not execute Asset Processor
- does not modify source art assets
- does not spawn or publish
- does not read Cache or live asset databases

## Report Contract

Schema:

- `schemas/maxine_dcc_conform_report.schema.json`

Core report fields:

- identity and routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- target contract: `target.skeleton_contract_id`, `target.expected_skeleton_contract_id`, `target.package_tier`
- DCC evidence metadata: `dcc.tool_name`, optional `dcc.tool_version`, `dcc.export_preset`, `dcc.intended_output_path`, `dcc.evidence_only=true`
- transform evidence: units, normalization, origin, axes, handedness, bounds
- skeleton evidence: `root_bone_present`, `skeleton_contract_result`, optional `skeleton_validator_output_ref`
- structured findings list
- manifest attachment payload

## MAX_BIPED_v1 Integration

- DCC conform reports must target `MAX_BIPED_v1`.
- Expected contract id is enforced by validator rule checks.
- Skeleton contract results can be referenced through `skeleton_validator_output_ref`.

## Manifest v1 Integration

Current attachment path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

DCC conform check id:

- `dcc_conform_v1`

The validator emits a normalized QC payload suitable for immediate attachment to the current manifest contract and forward migration to `qc.checks[]`.

## Validator

Validator script:

- `tools/dcc-conform/validate_dcc_conform_report.py`

Behavior:

- exits `0` for `pass`
- exits `0` for `warn` only when `--allow-warn` is supplied
- exits nonzero for `fail`
- exits nonzero for `warn` without `--allow-warn`

## Safety Boundaries

This slice remains evidence/report-validation only and preserves existing safety boundaries:

- no broad execution admissions
- no spawn/publish admissions
- no cache/live-db admissions
- no source/product UUID claim admissions
- no authoritative writes

## Future Path (Not Implemented Here)

A later slice may add bounded Blender/DCC execution with explicit approvals and sandbox-local evidence capture. That future work is not implemented in this slice.
