# Job Manifest Contract

This pipeline is **manifest-first**. Every job is represented by a machine-readable manifest that is updated as the job progresses.

## Required Top-Level Manifest Sections

Every manifest structure is expected to include these sections:

- `job`
- `identity`
- `inputs`
- `generation`
- `dcc_conform`
- `o3de`
- `qc`
- `runtime_validation`
- `evidence`
- `provenance`
- `undo`
- `cleanup`

## Manifest-First Rules

- A manifest is required for every job.
- Failed jobs must still emit a manifest.
- Pending/manual jobs must still emit a manifest.
- Evidence references and failure class data must be attached to the manifest, not only console logs.

## Draft vs Release Requirements

- Draft jobs are allowed to use a lighter subset of fields in generation/runtime details.
- Release jobs require stricter and more complete fields, including canonical source identity, product resolution, QC gate outcomes, and rollback/cleanup data.

The contract is designed so automation, operators, and CI can evaluate a job state from the manifest alone.

## Skeleton QC Attachment Point

- `MAX_BIPED_v1` skeleton validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `max_biped_v1_skeleton_contract`.

## DCC Conform QC Attachment Point

- `DCC_CONFORM_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `dcc_conform_v1`.

## Material/UV QC Attachment Point

- `MATERIAL_UV_QC_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `material_uv_qc_v1`.

## Animation Smoke QC Attachment Point

- `ANIMATION_SMOKE_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `animation_smoke_v1`.

## Screenshot Evidence QC Attachment Point

- `SCREENSHOT_EVIDENCE_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `screenshot_evidence_v1`.

## Manual Hero Review QC Attachment Point

- `MANUAL_HERO_REVIEW_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `manual_hero_review_v1`.

## CI Artifact Retention QC Attachment Point

- `CI_ARTIFACT_RETENTION_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `ci_artifact_retention_v1`.

## Release Package Bundle QC Attachment Point

- `RELEASE_PACKAGE_BUNDLE_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_package_bundle_v1`.

## Release Promotion Decision QC Attachment Point

- `RELEASE_PROMOTION_DECISION_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_promotion_decision_v1`.

## Release Publication Preflight QC Attachment Point

- `RELEASE_PUBLICATION_PREFLIGHT_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_preflight_v1`.

## Release Publication Request Approval QC Attachment Point

- `RELEASE_PUBLICATION_REQUEST_APPROVAL_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_request_approval_v1`.

## Release Publication Execution Admission Gate QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_ADMISSION_GATE_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_admission_gate_v1`.

## Release Publication Execution Request Ledger QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_REQUEST_LEDGER_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_request_ledger_v1`.

## Release Publication Execution Receipt QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_RECEIPT_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_receipt_v1`.

## Release Publication Rollback Drill QC Attachment Point

- `RELEASE_PUBLICATION_ROLLBACK_DRILL_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_rollback_drill_v1`.

## Release Publication Evidence Integrity Index QC Attachment Point

- `RELEASE_PUBLICATION_EVIDENCE_INTEGRITY_INDEX_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_evidence_integrity_index_v1`.

## Release Publication Chain Audit Bundle QC Attachment Point

- `RELEASE_PUBLICATION_CHAIN_AUDIT_BUNDLE_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_chain_audit_bundle_v1`.

## Release Publication Ready For Execution Request QC Attachment Point

- `RELEASE_PUBLICATION_READY_FOR_EXECUTION_REQUEST_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_ready_for_execution_request_v1`.

## Release Publication Execution Handoff QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_HANDOFF_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_handoff_v1`.

## Release Publication Execution Admission Request Packet QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_ADMISSION_REQUEST_PACKET_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_admission_request_packet_v1`.

## Release Publication Execution Admission Review QC Attachment Point

- `RELEASE_PUBLICATION_EXECUTION_ADMISSION_REVIEW_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_execution_admission_review_v1`.
