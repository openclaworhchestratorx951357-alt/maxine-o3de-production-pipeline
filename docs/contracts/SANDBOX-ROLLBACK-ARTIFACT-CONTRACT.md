# Sandbox Rollback Artifact Contract

Required future rollback fields:

- `schema_version`
- `rollback_id`
- `sandbox_id`
- `source_manifest`
- `target_manifest_copy`
- `pre_write_snapshot`
- `pre_write_snapshot_sha256`
- `proposed_post_write_state`
- `proposed_field_changes`
- `rollback_actions`
- `rollback_report_path`
- `operator_approval_ref`
- `execution_gate_ref`
- `safety`

Required safety flags:

- `read_only_contract: true`
- `rollback_execution_implemented: false`
- `sandbox_write_implemented: false`
- `production_paths_allowed: false`
- `o3de_engine_modification_allowed: false`
- `maxineshow_project_modification_allowed: false`
- `asset_processor_allowed: false`
- `o3de_editor_allowed: false`
- `prefab_publication_allowed: false`
- `entity_spawn_allowed: false`
- `real_asset_ids_allowed: false`

Reserved future rollback command name (not implemented):

`Invoke-MaxineSandboxRollback.ps1`

This command is not implemented in this phase.
