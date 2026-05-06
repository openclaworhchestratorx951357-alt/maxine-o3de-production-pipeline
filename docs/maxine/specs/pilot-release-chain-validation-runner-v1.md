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
- runs controlled screenshot/visual evidence validation:
  - `screenshot_evidence_v1`
- runs manual hero review validator evidence (requires controlled-real gate references for hero tier):
  - `manual_hero_review_v1`
- runs AAA performance budget validator evidence:
  - `aaa_performance_budget_v1`
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
- runs release publication evidence integrity index validator evidence:
  - `release_publication_evidence_integrity_index_v1`
- runs release publication chain audit bundle validator evidence:
  - `release_publication_chain_audit_bundle_v1`
- attaches fixture-backed rollback/readiness evidence payloads:
  - `release_publication_rollback_drill_v1`
  - `release_publication_ready_for_execution_request_v1`
- runs release publication execution handoff validator evidence:
  - `release_publication_execution_handoff_v1`
- runs release publication execution admission request packet validator evidence:
  - `release_publication_execution_admission_request_packet_v1`
- runs release publication gate-set validator evidence:
  - `release_publication_gate_set_v1`
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

Strict mode (expected zero when chain remains pass):

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
- controlled-real fixture inputs used by runner:
  - `examples/sandbox/max-biped-skeleton-evidence/pilot-candidates/max_biped_v1_skeleton_controlled_real.fixture.json`
  - `examples/sandbox/dcc-conform-evidence/pilot-candidates/max_biped_v1_dcc_conform_controlled_real.fixture.json`
  - `examples/sandbox/material-uv-evidence/pilot-candidates/max_biped_v1_material_uv_controlled_real.fixture.json`
  - `examples/sandbox/animation-smoke-evidence/pilot-candidates/max_biped_v1_animation_smoke_controlled_real.fixture.json`
  - `examples/sandbox/visual-evidence/pilot-candidates/max_biped_v1_visual_evidence_controlled_real.fixture.json`
  - `examples/sandbox/manual-hero-review-evidence/pilot-candidates/max_biped_v1_manual_hero_review_controlled_real.fixture.json`
  - `examples/sandbox/aaa-performance-budget-evidence/pilot-candidates/max_biped_v1_aaa_performance_budget_controlled_real.fixture.json`
- runtime-artifact policy:
  - `examples/sandbox/manifests/reports/**` is runtime-only and gitignored (except `.gitkeep`)

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
  - `aaa_performance_budget_v1`
  - `ci_artifact_retention_v1`
  - `release_package_bundle_v1`
  - `release_promotion_decision_v1`
  - `release_publication_preflight_v1`
  - `release_publication_request_approval_v1`
  - `release_publication_execution_admission_gate_v1`
  - `release_publication_execution_request_ledger_v1`
  - `release_publication_execution_receipt_v1`
  - `release_publication_evidence_integrity_index_v1`
  - `release_publication_chain_audit_bundle_v1`
  - `release_publication_rollback_drill_v1`
  - `release_publication_ready_for_execution_request_v1`
  - `release_publication_execution_handoff_v1`
  - `release_publication_execution_admission_request_packet_v1`
  - `release_publication_gate_set_v1`
  - `pilot_release_chain_v1`

## Safety Boundaries

- no Blender or DCC execution admission
- no O3DE execution admission
- no real/broad Asset Processor execution admission
- no spawn/publish admission
- no Cache/live DB access admission
- no source/product UUID claim admission
- no authoritative write admission
