# Sandbox Fixture Path-Safety Contract

This contract defines path-safety requirements for a future sandbox-only write prototype.

Required future fields:

- `sandbox_root`
- `allowed_relative_roots`
- `forbidden_path_patterns`
- `required_fixture_directories`
- `path_checks`
- `rejected_paths`
- `accepted_paths`
- `safety`

Required safety flags:

- `read_only_contract`: true
- `sandbox_write_implemented`: false
- `rollback_execution_implemented`: false
- `production_paths_allowed`: false
- `absolute_paths_allowed`: false
- `parent_traversal_allowed`: false
- `o3de_engine_modification_allowed`: false
- `maxineshow_project_modification_allowed`: false
- `asset_processor_allowed`: false
- `o3de_editor_allowed`: false

This contract does not authorize writes.
