# Sandbox Execution Intent and Hold Contract

This contract defines execution intent and execution-hold validation requirements after sandbox write final preflight.

Future validation command:

- `Test-MaxineSandboxExecutionIntent.ps1`

Command status:

- validator only, no writes

Required inputs:

- `final_preflight_report_path`
- `execution_intent_path`
- `execution_hold_path`
- `acceptance_decision`

Allowed intent status values:

- `intent_recorded`
- `intent_blocked`
- `intent_hold`

Allowed hold status values:

- `hold_active`
- `hold_released`

For this phase, hold status must be:

- `hold_active`

Safety flags:

- `execution_intent_only`: true
- `execution_hold_active`: true
- `implementation_available`: false
- `sandbox_write_allowed`: false
- `rollback_execution_allowed`: false
- `authoritative_write_allowed`: false
- `production_paths_allowed`: false
- `product_resolution_allowed`: false
- `asset_id_claims_allowed`: false

This contract records intent and hold status but does not authorize or execute writes.
