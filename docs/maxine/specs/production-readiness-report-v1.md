# Production Readiness Report v1

`production_readiness_report_v1` provides a truthful readiness summary for the current M.A.X.I.N.E. release lane.

It is explicitly evidence-only in this milestone and does not admit execution or publication.

## Contract

- report type: `PRODUCTION_READINESS_REPORT_v1_REPORT`
- check id: `production_readiness_report_v1`
- contract id: `PRODUCTION_READINESS_REPORT_v1`
- current attachment target: `qc.gates[]`
- future attachment target: `qc.checks[]`

## Scope

The report distinguishes and records:

- evidence-only release-candidate readiness
- controlled-real/imported/manual/fixture evidence split
- admitted no-op receipt candidates and receipt-backed candidate ids
- admitted real-execution candidates (separate from no-op receipt admission)
- admitted publication candidates (separate from no-op receipt admission)
- AAA-quality gate readiness
- execution admission posture
- publication admission posture
- execution-admission candidate matrix and preflight-contract requirement posture
- remaining blockers before true production operation

## Required Gate Coverage

The report consumes the integrated gate set, including:

- release-lane chain gates through `release_publication_gate_set_v1`
- `pilot_release_chain_v1`
- `real_pilot_release_candidate_package_v1`

It fails when required gate-chain summary coverage is missing.

## Readiness Policy

- evidence-ready/review-ready may be recognized when required evidence gates pass.
- no-op receipt admission is tracked separately and does not satisfy real execution admission.
- candidate-specific preflight contracts are tracked as requirements only and do not satisfy execution/publication admission.
- execution-ready remains blocked unless explicit real-execution candidate admission exists with reference evidence.
- production-ready remains blocked unless both execution and publication are explicitly admitted.
- source/product authority remains evidence-only/not-authoritative unless an admitted authority path exists.
- the report must not claim `production_ready` while blocked surfaces remain blocked.

## Safety Posture

No execution or publication is admitted by this report:

- no O3DE execution
- no Editor/runtime execution
- no profiler/benchmark execution
- no real/broad Asset Processor execution
- no Blender/DCC execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production path writes
- no engine path writes

## Implementation

- schema:
  - `schemas/maxine_production_readiness_report.schema.json`
- validator:
  - `tools/production-readiness-report/validate_production_readiness_report.py`
- examples:
  - `examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json`
  - `examples/production-readiness-report/max_biped_v1_production_readiness_report_warn.json`
  - `examples/production-readiness-report/max_biped_v1_production_readiness_report_fail.json`
- runner/proof integration:
  - `tools/release-lane/run_pilot_release_chain_validation.py`
  - `tools/release-lane/prove_pilot_release_chain.py`

## Follow-On Planning

Execution/publication remains blocked for real tool execution and publication. The first narrow no-op receipt candidate is now admitted only for bounded receipt generation, and remains non-executing/non-publishing:

- `docs/maxine/execution-admission/execution-publication-admission-planning-v1.md`
- `docs/maxine/execution-admission/release-candidate-package-receipt-noop-v1.md`
- `docs/maxine/execution-admission/execution-admission-candidate-matrix-v1.md`
- `docs/maxine/execution-admission/execution-admission-preflight-contracts-v1.md`
- `examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json`
