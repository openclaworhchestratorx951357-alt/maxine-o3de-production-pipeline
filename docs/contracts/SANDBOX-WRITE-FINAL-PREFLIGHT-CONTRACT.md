# Sandbox Write Final Preflight Contract

This contract defines final preflight validation requirements for a future sandbox write attempt.

Future validation command:

- `Test-MaxineSandboxWriteFinalPreflight.ps1`

Command status:

- validator only, no writes

Required inputs:

- `sandbox_write_plan_path`
- `dry_run_report_path`
- `approval_gate_report_path`
- `rollback_artifact_path`
- `acceptance_decision`

Allowed status values:

- `preflight_ready`
- `preflight_blocked`
- `preflight_incomplete`

Required checks:

- `accepted_decision`
- `sandbox_write_plan_valid`
- `dry_run_report_ready`
- `approval_gate_report_ready`
- `approval_references_consistent`
- `rollback_artifact_valid`
- `implementation_commands_absent`

Safety flags:

- `preflight_only`: true
- `implementation_available`: false
- `sandbox_write_allowed`: false
- `rollback_execution_allowed`: false
- `authoritative_write_allowed`: false
- `production_paths_allowed`: false
- `product_resolution_allowed`: false
- `asset_id_claims_allowed`: false

This contract validates final preflight readiness for a future sandbox write attempt but does not execute writes.
