# Pilot Release Chain CI Proof v1

## Purpose

`pilot_release_chain_ci_proof_v1` provides one deterministic local/CI command that proves the implemented release-lane validator chain is connected through Manifest v1 attachments.

Command:

```powershell
python tools/release-lane/prove_pilot_release_chain.py
```

## What It Does

- runs `run_pilot_release_chain_validation.py` once in normal mode
- runs `run_pilot_release_chain_validation.py` once in `--strict-chain` mode
- runs `report_release_lane_evidence_admission_status.py` against the strict-run generated manifest
- runs `generate_execution_admission_receipt_dry_run.py` using the approved execution-admission decision fixture
- runs `validate_command_pack_admission_precheck_report.py` as read-only proof evidence
- verifies expected behavior for the current fixture baseline:
  - normal mode succeeds with `pilot_chain_status=pass`
  - strict mode also succeeds when `pilot_chain_status=pass`
  - evidence-admission status report succeeds with `status=pass`
  - execution-admission receipt dry-run report succeeds with `status=pass` and `execution_performed=false`
  - command-pack admission precheck succeeds with `status=pass` while keeping `admission_request_eligible=false`
- writes proof summary JSON under sandbox-local report paths
- treats `examples/sandbox/manifests/reports/**` as runtime-only artifacts (gitignored except `.gitkeep`)

Proof artifacts include:

- `examples/sandbox/manifests/reports/pilot-release-chain-proof/proof-summary.json`
- `examples/sandbox/manifests/reports/pilot-release-chain-proof/release-lane-evidence-admission-status.json`
- `examples/sandbox/manifests/reports/pilot-release-chain-proof/execution-admission-receipt-dry-run.json`

## Safety Boundaries

- evidence-only orchestration
- no O3DE execution
- no command admission or approval-ready claim
- no Asset Processor execution admission
- no Blender/DCC execution
- no Cache/live DB access
- no spawn/publish
- no authoritative writes
- no runner or Gem adapter implementation
- no production-ready claim

## Manifest Integration

- current attachment path remains `qc.gates[]`
- future-compatible path remains `qc.checks[]`
- this command validates attachment flow; it does not widen gate semantics
