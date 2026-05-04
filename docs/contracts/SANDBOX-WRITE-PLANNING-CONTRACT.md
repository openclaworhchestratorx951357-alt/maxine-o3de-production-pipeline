# Sandbox Write Planning Contract

This contract defines planning requirements for a future sandbox-only write prototype.

Future command:

- `Invoke-MaxineSandboxResolverWrite.ps1`

Command status:

- not implemented

Future required inputs:

- `sandbox_write_plan_path`
- `confirm_sandbox_write`
- `sandbox_root`
- `target_manifest_copy`
- `pre_write_snapshot`
- `rollback_artifact`
- `operator_approval_ref`
- `execution_gate_ref`

Future proposed sandbox-only writable fields:

- `o3de.sandbox_proposed.review_only_flag`
- `o3de.sandbox_proposed.proof_refs`
- `o3de.sandbox_proposed.rollback_ref`
- `o3de.sandbox_proposed.sandbox_only_resolution_marker`
- `o3de.sandbox_proposed.operator_approval_ref`

Forbidden fields:

- `o3de.products.resolved`
- `o3de.products.asset_id`
- `o3de.products.resolved_products`
- real product Asset IDs
- prefab publication output
- entity spawn output

Future safety flags:

- `sandbox_only`: true
- `implementation_available`: false
- `sandbox_write_allowed`: false
- `rollback_execution_required`: true
- `rollback_execution_implemented`: false
- `authoritative_write_allowed`: false
- `production_paths_allowed`: false
- `product_resolution_allowed`: false
- `asset_id_claims_allowed`: false

This contract is for future sandbox write planning only and does not implement writes.

This command is not implemented.
