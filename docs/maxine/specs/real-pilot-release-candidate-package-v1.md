# Real Pilot Release Candidate Package v1

`real_pilot_release_candidate_package_v1` defines an evidence-only package-proof contract that binds the implemented release-lane gates into one pilot release-candidate decision artifact.

## Contract

- report type: `REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1_REPORT`
- check id: `real_pilot_release_candidate_package_v1`
- contract id: `REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1`
- current attachment target: `qc.gates[]`
- future attachment target: `qc.checks[]`

## Required Gate References

- `source_product_evidence_resolver_v1`
- `dcc_conform_v1`
- `max_biped_v1_skeleton_contract`
- `material_uv_qc_v1`
- `animation_smoke_v1`
- `screenshot_evidence_v1`
- `manual_hero_review_v1`
- `aaa_performance_budget_v1`
- `release_package_bundle_v1`
- `release_promotion_decision_v1`
- `release_publication_preflight_v1`
- `release_publication_gate_set_v1`
- `pilot_release_chain_v1`

## Evidence-Class Policy

Core AAA gates must not rely only on fixture evidence:

- source/product resolver: imported or controlled_real
- DCC conform: controlled_real
- MAX_BIPED skeleton: controlled_real
- material/UV: controlled_real
- animation smoke: controlled_real
- screenshot/visual: controlled_real
- manual hero review: manual or controlled_real
- AAA performance budget: controlled_real

## Pass/Warn/Fail Policy

- `pass`:
  - all required gate refs present
  - no fail/pending required gate results
  - core evidence class policy satisfied
  - no false execution/publication admission signals
- `warn`:
  - required chain present with non-blocking warn signals
- `fail`:
  - required gate refs missing
  - required gate fail result
  - core evidence class policy violation
  - false execution/publication admission signal
- `pending`:
  - required gate result is `pending_manual`

## Safety Posture

This slice is evidence-only and keeps execution/publication blocked:

- no O3DE execution
- no Editor/runtime execution
- no real/broad Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production path writes
- no engine path writes

## Implementation

- schema:
  - `schemas/maxine_real_pilot_release_candidate_package_report.schema.json`
- validator:
  - `tools/real-pilot-release-candidate-package/validate_real_pilot_release_candidate_package_report.py`
- examples:
  - `examples/real-pilot-release-candidate-package/max_biped_v1_real_pilot_release_candidate_package_pass.json`
  - `examples/real-pilot-release-candidate-package/max_biped_v1_real_pilot_release_candidate_package_warn.json`
  - `examples/real-pilot-release-candidate-package/max_biped_v1_real_pilot_release_candidate_package_fail.json`
- runner integration:
  - `tools/release-lane/run_pilot_release_chain_validation.py`
