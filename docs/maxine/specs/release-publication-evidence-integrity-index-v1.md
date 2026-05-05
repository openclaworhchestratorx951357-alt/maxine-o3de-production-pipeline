# Release Publication Evidence Integrity Index v1 (Evidence-Only)

## What This Slice Does

`Release publication evidence integrity index v1` defines an evidence-only contract for recording immutable hash coverage and completeness of the release publication evidence chain.

- validates structured evidence-integrity-index report JSON
- checks required release QC gate coverage before audit-ready decision
- checks required evidence artifact hash-index completeness
- checks manual approval threshold and rollback/cleanup verification
- checks immutable evidence bundle path/hash/artifact evidence
- checks command execution remains unadmitted and unrecorded
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not execute publication commands
- does not admit publication execution
- does not spawn runtime entities
- does not read Cache or live asset databases
- does not perform destructive cleanup

## Report Contract

Schema:

- `schemas/maxine_release_publication_evidence_integrity_index_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- index contract:
  - `contract_id=RELEASE_PUBLICATION_EVIDENCE_INTEGRITY_INDEX_v1`
  - `required_gate_ids`
  - `required_artifact_ids`
  - `required_approvals`
  - `manual_review_required`
  - `immutable_index_required=true`
  - `hash_verification_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- evidence integrity index:
  - `index_id`
  - `index_recorded_utc`
  - `recorded_by`
  - `index_action=record_release_publication_evidence_integrity_index`
  - `index_scope=release_publication_chain`
  - `execution_receipt_id`
  - `rollback_drill_id`
  - `hash_algorithm=sha256`
  - `artifact_hash_index`
  - `artifact_count`
  - `hash_verification_status`
  - `missing_artifact_ids`
  - `hash_mismatch_artifact_ids`
  - `manifest_reference_path`
  - `no_command_execution_recorded=true`
  - `evidence_bundle_path`
  - `evidence_bundle_sha256`
  - `evidence_bundle_artifacts`
  - `evidence_bundle_immutable=true`
- approval state:
  - `decision` (`integrity_index_recorded_for_audit|pending_manual_review|rejected`)
  - `approver_ids`
  - `blocked_reason_codes`
  - `rollback_plan_verified`
  - `cleanup_plan_verified`
  - all execution-admission flags remain `false`
- readiness:
  - `required_gate_ids`
  - `present_gate_ids`
  - `missing_gate_ids`
  - `integrity_readiness_state`
- findings
- manifest attachment payload

## Validation Logic

- missing required gates is fail-level
- missing required hash-index artifacts is fail-level
- pass hash-verification status with missing/mismatched artifacts is fail-level
- audit-ready decision with insufficient approvals is fail-level
- audit-ready decision with blocked reasons is fail-level
- audit-ready decision without rollback/cleanup verification is fail-level
- pending manual review decision is manual-review status
- rejected decision is fail-level
- unsafe path tokens for manifest/bundle/artifacts are blocked
- disallowed runtime/cache/database artifacts are blocked
- all execution-admission flags remain false

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_evidence_integrity_index_v1`

## Validator

Validator script:

- `tools/release-publication-evidence-integrity-index/validate_release_publication_evidence_integrity_index_report.py`

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
- no spawn/publish execution admission
- no Cache/live DB access
- no source/product UUID claims
- no new generation lanes
- no destructive cleanup

## Future Path (Not Implemented Here)

A future admitted publication-control slice may consume this integrity index as a mandatory audit input before any live publication execution admission. This v1 slice remains non-executing and non-admitting.
