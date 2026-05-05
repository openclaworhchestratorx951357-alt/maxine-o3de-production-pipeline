# Pilot Release Chain Validation Runner v1

## What This Slice Does

`run_pilot_release_chain_validation.py` connects existing validators into one deterministic local command.

- starts from a pilot base manifest fixture
- runs implemented validators:
  - `max_biped_v1_skeleton_contract`
  - `dcc_conform_v1`
  - `source_product_evidence_resolver_v1`
  - `material_uv_qc_v1`
  - `animation_smoke_v1`
- runs controlled screenshot evidence extraction:
  - `screenshot_evidence_v1`
- runs manual hero review validator evidence:
  - `manual_hero_review_v1`
- runs CI artifact retention validator evidence:
  - `ci_artifact_retention_v1`
- runs release package bundle validator evidence:
  - `release_package_bundle_v1`
- runs release promotion decision validator evidence:
  - `release_promotion_decision_v1`
- runs release publication preflight validator evidence:
  - `release_publication_preflight_v1`
- runs release publication request approval validator evidence:
  - `release_publication_request_approval_v1`
- runs release publication execution admission gate validator evidence:
  - `release_publication_execution_admission_gate_v1`
- runs release publication execution request ledger validator evidence:
  - `release_publication_execution_request_ledger_v1`
- runs release publication execution receipt validator evidence:
  - `release_publication_execution_receipt_v1`
- attaches fixture-backed rollback/readiness evidence payloads:
  - `release_publication_rollback_drill_v1`
  - `release_publication_ready_for_execution_request_v1`
- writes each validator payload snapshot
- attaches payloads into an output manifest using `attach_qc_gate.py`
- runs `pilot_release_chain_v1` validation on the generated manifest
- attaches the `pilot_release_chain_v1` payload into the same manifest
- writes a run summary JSON

This is integration execution for evidence payload processing only. It does not widen engine/AP/DCC runtime execution.

## Command

```powershell
python tools/release-lane/run_pilot_release_chain_validation.py
```

Strict mode (expected nonzero while chain remains warn):

```powershell
python tools/release-lane/run_pilot_release_chain_validation.py --strict-chain
```

## Inputs and Outputs

- base manifest:
  - `examples/manifests/example-release-character-pilot-chain-base.manifest.json`
- default output manifest:
  - `examples/sandbox/manifests/reports/example-release-character-pilot-chain.generated.manifest.json`
- payload snapshots and summary:
  - `examples/sandbox/manifests/reports/pilot-release-chain-validation/`

## Manifest Integration Point

- current target path: `qc.gates[]`
- future target path: `qc.checks[]`
- attached check IDs:
  - `max_biped_v1_skeleton_contract`
  - `dcc_conform_v1`
  - `source_product_evidence_resolver_v1`
  - `material_uv_qc_v1`
  - `animation_smoke_v1`
  - `screenshot_evidence_v1`
  - `manual_hero_review_v1`
  - `ci_artifact_retention_v1`
  - `release_package_bundle_v1`
  - `release_promotion_decision_v1`
  - `release_publication_preflight_v1`
  - `release_publication_request_approval_v1`
  - `release_publication_execution_admission_gate_v1`
  - `release_publication_execution_request_ledger_v1`
  - `release_publication_execution_receipt_v1`
  - `release_publication_rollback_drill_v1`
  - `release_publication_ready_for_execution_request_v1`
  - `pilot_release_chain_v1`

## Safety Boundaries

- no Blender or DCC execution admission
- no O3DE execution admission
- no real/broad Asset Processor execution admission
- no spawn/publish admission
- no Cache/live DB access admission
- no source/product UUID claim admission
- no authoritative write admission
