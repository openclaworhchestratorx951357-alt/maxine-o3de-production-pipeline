# Release Execution Receipt Dry-Run Framework v1

## Purpose

Define a bounded, non-destructive execution-receipt proof step that follows execution-admission decisions without admitting real execution in this slice.

This framework is evidence-only and no-op.

## Scope

- consumes an execution-admission decision record
- verifies approval phrase consistency for the candidate id
- records a dry-run receipt artifact
- records `execution_performed=false`
- records `no_command_execution_recorded=true`

This slice does not run O3DE, Asset Processor, Blender/DCC, spawn, publish, Cache, or live DB operations.

## Contract

Dry-run receipt report schema:

- `schemas/maxine_execution_admission_receipt_dry_run_report.schema.json`

Fixture example:

- `examples/execution-admission/max_biped_v1_execution_admission_receipt_dry_run_pass.json`

## Proof Command

Dry-run receipt generator:

- `python tools/release-lane/generate_execution_admission_receipt_dry_run.py`

Primary inputs:

- execution-admission decision record (default fixture):
  - `examples/execution-admission/max_biped_v1_execution_admission_decision_approved.json`

Primary output:

- `examples/sandbox/manifests/reports/pilot-release-chain-proof/execution-admission-receipt-dry-run.json`

## Proof-Flow Integration

The pilot CI proof now includes this dry-run receipt step:

- `python tools/release-lane/prove_pilot_release_chain.py`

Proof summary includes:

- `details.execution_admission_receipt_dry_run_report`

## Safety Boundaries

The framework preserves blocked/unadmitted surfaces:

- no broad O3DE execution
- no broad/real Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID claims
- no authoritative Asset ID claims
- no authoritative Product ID claims
- no production path writes
- no engine path writes

Execution admission remains future work requiring explicit operator approval.
