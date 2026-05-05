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

## Source Product Evidence Resolver QC Attachment Point

- `SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1` validation output is attachable to manifest QC.
- Current manifest attachment path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `source_product_evidence_resolver_v1`.
