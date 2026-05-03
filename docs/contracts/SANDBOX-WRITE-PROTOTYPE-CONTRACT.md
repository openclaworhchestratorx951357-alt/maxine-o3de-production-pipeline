# Sandbox Write Prototype Contract

This contract defines the proposed fields and safety constraints for a future sandbox-only write prototype.

No write execution is implemented in Phase 2.

## Proposed Future Contract Fields

- `sandbox_id`
- `sandbox_root`
- `source_manifest`
- `target_manifest_copy`
- `pre_write_snapshot`
- `proposed_write_fields`
- `rollback_plan`
- `rollback_report`
- `operator_approval_ref`
- `execution_gate_ref`
- `safety`

## Required Future Safety Flags

- `sandbox_only: true`
- `production_paths_allowed: false`
- `o3de_engine_modification_allowed: false`
- `maxineshow_project_modification_allowed: false`
- `asset_processor_allowed: false`
- `o3de_editor_allowed: false`
- `prefab_publication_allowed: false`
- `entity_spawn_allowed: false`
- `real_asset_ids_allowed: false`

## Reserved Future Command Name

`Invoke-MaxineSandboxResolverWrite.ps1`

This command is not implemented in Phase 2.
