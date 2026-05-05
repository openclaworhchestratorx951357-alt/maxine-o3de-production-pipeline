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
- verifies expected behavior for the current fixture baseline:
  - normal mode succeeds with `pilot_chain_status=pass`
  - strict mode also succeeds when `pilot_chain_status=pass`
- writes proof summary JSON under sandbox-local report paths

## Safety Boundaries

- evidence-only orchestration
- no O3DE execution
- no Asset Processor execution admission
- no Blender/DCC execution
- no Cache/live DB access
- no spawn/publish
- no authoritative writes

## Manifest Integration

- current attachment path remains `qc.gates[]`
- future-compatible path remains `qc.checks[]`
- this command validates attachment flow; it does not widen gate semantics
