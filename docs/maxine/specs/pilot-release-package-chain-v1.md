# Pilot Release Package Chain v1

## What This Slice Does

This slice connects existing release-lane QC validators into one deterministic pilot-chain check.

- defines a machine-readable gate chain fixture
- defines a representative pilot release manifest fixture
- validates required gate presence and order in `qc.gates[]`
- emits a manifest-attachable summary payload (`pilot_release_chain_v1`)

This is integration and consolidation work, not a new execution admission.

## Artifacts

- chain fixture:
  - `examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json`
- pilot manifest fixture:
  - `examples/manifests/example-release-character-pilot-chain.manifest.json`
- validator:
  - `tools/release-lane/validate_pilot_release_chain.py`
- tests:
  - `tests/pytest/test_pilot_release_chain.py`

## Validation Rules

The validator enforces:

- required gate IDs are present
- required gates appear in declared order
- duplicate `check_id` entries are rejected
- implemented gates cannot remain `pending_manual`
- unimplemented gates cannot be marked `pass`
- output always includes a manifest attachment payload:
  - current target: `qc.gates[]`
  - future target: `qc.checks[]`
  - check id: `pilot_release_chain_v1`

Exit behavior:

- `pass` -> exit `0`
- `warn` -> exit `0` only with `--allow-warn`
- `fail` -> nonzero

## Safety Boundaries

This slice remains evidence-only.

- no Blender or DCC execution
- no O3DE execution
- no real/broad Asset Processor execution
- no spawn/publish
- no Cache/live DB access
- no source/product UUID claim admission
- no authoritative writes
