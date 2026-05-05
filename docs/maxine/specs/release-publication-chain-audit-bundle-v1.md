# Release Publication Chain Audit Bundle v1 (Evidence-Only)

## What This Slice Does

`Release publication chain audit bundle v1` defines an evidence-only contract that aggregates the release publication chain into one immutable audit bundle with hash coverage.

- validates structured chain-audit-bundle report JSON
- checks required release QC gate completeness before audit-ready decision
- checks required report-artifact hash coverage and mismatch/missing tracking
- checks manual approval threshold and rollback/cleanup verification
- checks immutable chain audit bundle path/hash/artifact evidence
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

- `schemas/maxine_release_publication_chain_audit_bundle_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- bundle contract:
  - `contract_id=RELEASE_PUBLICATION_CHAIN_AUDIT_BUNDLE_v1`
  - `required_gate_ids`
  - `required_report_artifact_ids`
  - `required_approvals`
  - `manual_review_required`
  - `immutable_bundle_required=true`
  - `hash_verification_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- chain audit bundle:
  - `bundle_id`
  - `bundle_recorded_utc`
  - `recorded_by`
  - `bundle_action=record_release_publication_chain_audit_bundle`
  - `bundle_scope=release_publication_chain`
  - `promotion_decision_id`
  - `execution_receipt_id`
  - `rollback_drill_id`
  - `evidence_integrity_index_id`
  - `hash_algorithm=sha256`
  - `audit_bundle_artifact_hashes`
  - `artifact_count`
  - `bundle_verification_status`
  - `missing_report_artifact_ids`
  - `hash_mismatch_report_artifact_ids`
  - `chain_manifest_path`
  - `no_command_execution_recorded=true`
  - `audit_bundle_path`
  - `audit_bundle_sha256`
  - `audit_bundle_artifacts`
  - `audit_bundle_immutable=true`
- approval state:
  - `decision` (`chain_audit_bundle_recorded_for_audit|pending_manual_review|rejected`)
  - `approver_ids`
  - `blocked_reason_codes`
  - `rollback_plan_verified`
  - `cleanup_plan_verified`
  - all execution-admission flags remain `false`
- readiness:
  - `required_gate_ids`
  - `present_gate_ids`
  - `missing_gate_ids`
  - `chain_audit_bundle_readiness_state`
- findings
- manifest attachment payload

## Validation Logic

- missing required gates is fail-level
- missing required report-artifact hashes is fail-level
- pass verification status with missing/mismatched artifacts is fail-level
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

- `release_publication_chain_audit_bundle_v1`

## Validator

Validator script:

- `tools/release-publication-chain-audit-bundle/validate_release_publication_chain_audit_bundle_report.py`

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

A future admitted publication-control slice may require this chain audit bundle as a mandatory audit artifact before any live publication execution admission.
