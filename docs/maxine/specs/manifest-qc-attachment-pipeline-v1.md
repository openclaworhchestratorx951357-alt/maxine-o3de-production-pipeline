# Manifest QC Attachment Pipeline v1

## What This Slice Does

`manifest-qc-attachment-pipeline-v1` provides deterministic manifest integration for validator QC payloads.

- reads one manifest JSON
- reads one-or-more validator output JSON payloads
- validates attachment payload shape and required fields
- appends `qc_check` entries to `qc.gates[]` or `qc.checks[]`
- blocks duplicate `check_id` by default
- recomputes `qc.overall` deterministically from attached check results
- preserves unknown manifest fields
- writes manifest updates atomically

## What This Slice Does Not Do

- does not execute Blender/DCC tools
- does not execute O3DE
- does not execute Asset Processor
- does not read live Cache or live asset database
- does not admit source/product UUID authoritative claims
- does not spawn or publish

## Tooling

- attach tool: `tools/manifest-validator/attach_qc_gate.py`
- attachment schema: `schemas/maxine_manifest_qc_attachment.schema.json`
- example attachment payloads:
  - `examples/manifest-qc-attachments/max_biped_v1_skeleton_attach_pass.json`
  - `examples/manifest-qc-attachments/max_biped_v1_dcc_conform_attach_warn.json`
  - `examples/manifest-qc-attachments/max_biped_v1_source_product_attach_fail.json`
- base manifest fixture:
  - `examples/manifests/example-release-character-qc-attach-base.manifest.json`

## Manifest Integration Point

- current attachment target: `qc.gates[]`
- future-compatible target: `qc.checks[]`

## Safety Boundaries

- manifest and attachment paths must remain inside repository root
- blocked path tokens include cache/engine/git internals
- duplicate check IDs are rejected unless explicitly allowed
- malformed attachments are rejected

This slice is manifest/evidence integration only and does not widen execution admissions.
