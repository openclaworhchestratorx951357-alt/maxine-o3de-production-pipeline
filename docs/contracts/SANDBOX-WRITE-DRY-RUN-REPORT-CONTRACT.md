# Sandbox Write Dry-Run Report Contract

This contract defines dry-run validation requirements for a future sandbox write plan.

Future validation command:

- `Test-MaxineSandboxWriteDryRun.ps1`

Command status:

- validator only, no writes

Required inputs:

- `sandbox_write_plan_path`
- `sandbox_write_plan`
- `rollback_artifact`
- `path_safety_policy`
- `acceptance_decision`
- `rollback_execution_design_plan`

Allowed status values:

- `dry_run_ready`
- `dry_run_blocked`
- `dry_run_incomplete`

Required checks:

- `accepted_decision`
- `sandbox_write_plan_valid`
- `target_path_safe`
- `rollback_artifact_valid`
- `rollback_execution_design_valid`
- `forbidden_fields_absent_from_proposed_changes`
- `implementation_commands_absent`

Safety flags:

- `dry_run_only`: true
- `implementation_available`: false
- `sandbox_write_allowed`: false
- `rollback_execution_allowed`: false
- `authoritative_write_allowed`: false
- `production_paths_allowed`: false
- `product_resolution_allowed`: false
- `asset_id_claims_allowed`: false

This contract validates a future sandbox write plan but does not execute writes.
