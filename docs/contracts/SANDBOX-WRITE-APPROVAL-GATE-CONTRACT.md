# Sandbox Write Approval Gate Contract

This contract defines approval-gate validation requirements for a future sandbox write attempt.

Future validation command:

- `Test-MaxineSandboxWriteApprovalGate.ps1`

Command status:

- validator only, no writes

Required inputs:

- `dry_run_report_path`
- `operator_approval_path`
- `sandbox_write_plan`
- `approval_scope`
- `acceptance_decision`

Allowed status values:

- `approval_ready`
- `approval_blocked`
- `approval_incomplete`

Required checks:

- `accepted_decision`
- `dry_run_report_ready`
- `approval_artifact_valid`
- `approval_scope_sandbox_only`
- `approval_references_dry_run_report`
- `implementation_commands_absent`

Safety flags:

- `approval_gate_only`: true
- `implementation_available`: false
- `sandbox_write_allowed`: false
- `rollback_execution_allowed`: false
- `authoritative_write_allowed`: false
- `production_paths_allowed`: false
- `product_resolution_allowed`: false
- `asset_id_claims_allowed`: false

This contract validates approval for a future sandbox write attempt but does not execute writes.
