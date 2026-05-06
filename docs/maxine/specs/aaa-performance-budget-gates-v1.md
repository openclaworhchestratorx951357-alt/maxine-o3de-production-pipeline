# AAA Performance Budget Gates v1

This slice integrates `aaa_performance_budget_v1` into the pilot release-lane chain using controlled fixture/import evidence only.

## What Is Integrated

- schema: `schemas/maxine_aaa_performance_budget_report.schema.json`
- validator: `tools/aaa-performance-budget/validate_aaa_performance_budget_report.py`
- examples:
  - `examples/aaa-performance-budget/max_biped_v1_aaa_performance_budget_pass.json`
  - `examples/aaa-performance-budget/max_biped_v1_aaa_performance_budget_warn.json`
  - `examples/aaa-performance-budget/max_biped_v1_aaa_performance_budget_fail.json`
  - `examples/sandbox/aaa-performance-budget-evidence/pilot-candidates/max_biped_v1_aaa_performance_budget_controlled_real.fixture.json`
- pilot runner integration:
  - `tools/release-lane/run_pilot_release_chain_validation.py`
- chain integration:
  - `examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json`
  - `examples/manifests/example-release-character-pilot-chain.manifest.json`
- evidence admission classification integration:
  - `tools/release-lane/report_release_lane_evidence_admission_status.py`

## Behavior

- required pilot release-lane gate now includes `aaa_performance_budget_v1`
- performance budget evidence is validated and attached into `qc.gates[]`
- evidence class for the integrated fixture path is `controlled_real`
- pass/warn/fail behavior is supported
- explicit waivers are required and visibly reported when used

## Safety Boundaries Preserved

- no O3DE execution
- no editor/runtime execution
- no profiler/benchmark execution
- no Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production/engine path writes

This slice is evidence-only and does not admit execution or publication.
