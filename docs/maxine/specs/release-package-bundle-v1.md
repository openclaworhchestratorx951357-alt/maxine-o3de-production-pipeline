# Release Package Bundle v1 (Evidence-Only)

## What This Slice Does

`Release package bundle v1` defines an evidence-only contract for deterministic release-package bundle structure, artifact inventory, and rollback/cleanup instruction coverage.

- validates structured release package bundle report JSON
- checks deterministic bundle layout contract fields
- checks required bundle artifacts and missing/disallowed path reporting
- checks release-lane determinism evidence and rollback instruction coverage
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not spawn or publish
- does not read Cache or live asset databases
- does not perform destructive cleanup

## Report Contract

Schema:

- `schemas/maxine_release_package_bundle_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- bundle contract:
  - `contract_id=RELEASE_PACKAGE_BUNDLE_v1`
  - `bundle_root`
  - `expected_manifest_path`
  - `expected_artifact_index_path`
  - `expected_rollback_plan_path`
  - `expected_cleanup_plan_path`
  - `deterministic_layout=true`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
- bundle inventory:
  - `manifest_path`
  - `artifact_index_path`
  - `rollback_plan_path`
  - `cleanup_plan_path`
  - `included_paths`
  - `missing_paths`
  - `disallowed_paths`
- determinism:
  - `package_id_stable`
  - `input_provenance_recorded`
  - `source_product_tracking_recorded`
  - `product_resolution_mode`
  - `checksum_index_present`
- rollback/cleanup:
  - `undo_available`
  - `rollback_step_count`
  - `rollback_instruction_paths`
  - `cleanup_step_count`
  - `cleanup_instruction_paths`
  - `destructive_cleanup_admitted=false`
- release readiness:
  - `readiness_state`
  - `manual_review_required`
- findings
- manifest attachment payload

## Validation Logic

- Missing expected bundle paths is fail-level.
- Disallowed paths is fail-level.
- Unsafe traversal or absolute path tokens is fail-level.
- `proposal_only` product resolution mode is warn-level.
- Missing rollback/cleanup instructions is fail-level.
- Release-character readiness must keep manual review required.

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_package_bundle_v1`

## Validator

Validator script:

- `tools/release-package-bundle/validate_release_package_bundle_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `warn` without `--allow-warn`
- exits nonzero on `fail`
- exits nonzero on `pending_manual`

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

A future slice may connect this contract to actual package publication and rollback orchestration. That execution surface is not implemented in v1.
