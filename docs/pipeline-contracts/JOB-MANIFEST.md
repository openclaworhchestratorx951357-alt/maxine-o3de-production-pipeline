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

- `SCREENSHOT_EVIDENCE_EXTRACTOR_v1` output is attachable to manifest QC.
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

## Rollback Drill QC Attachment Point

- `RELEASE_PUBLICATION_ROLLBACK_DRILL_v1` evidence payload is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_rollback_drill_v1`.

## Ready-for-Execution Request QC Attachment Point

- `RELEASE_PUBLICATION_READY_FOR_EXECUTION_REQUEST_v1` evidence payload is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `release_publication_ready_for_execution_request_v1`.

## Pilot Chain Proof Attachment Flow

- `pilot_release_chain_ci_proof_v1` validates that implemented validator outputs are attachable in deterministic sequence.
- Local/CI proof command: `python tools/release-lane/prove_pilot_release_chain.py`.
- Current attachment path remains `qc.gates[]` and future-compatible path remains `qc.checks[]`.

## Pilot Chain Integration Runner

Deterministic local integration command:

- `python tools/release-lane/run_pilot_release_chain_validation.py`

It runs implemented validators, writes payload snapshots, attaches QC payloads into one manifest, validates `pilot_release_chain_v1`, and attaches that chain result payload.

## Source Product Evidence Resolver QC Attachment Point

- `SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1` report validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `source_product_evidence_resolver_v1`.

## Deterministic QC Attachment Pipeline

Manifest QC payload attachment is deterministic and script-driven:

- script: `tools/manifest-validator/attach_qc_gate.py`
- input: one manifest path and one-or-more validator attachment payload JSON files
- behavior:
  - validates attachment payload shape
  - appends `qc_check` payloads to `qc.gates[]` or `qc.checks[]`
  - blocks duplicate `check_id` by default
  - preserves unknown manifest fields
  - writes atomically

This is evidence integration only. It does not admit O3DE/AP execution, spawn/publish, or live Cache/DB access.

## Pilot Chain Attachment Point

- `PILOT_RELEASE_CHAIN_v1` validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `pilot_release_chain_v1`.
- Pilot manifest fixture:
  - `examples/manifests/example-release-character-pilot-chain.manifest.json`.
