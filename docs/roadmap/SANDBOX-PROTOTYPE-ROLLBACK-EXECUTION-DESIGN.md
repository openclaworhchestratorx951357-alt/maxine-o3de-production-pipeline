# Sandbox Prototype Rollback Execution Design

## 1. Purpose

This document defines the future rollback execution design for a sandbox-only write prototype.

## 2. Non-goals

- rollback execution is not implemented
- sandbox writes are not implemented
- authoritative writes are not implemented
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs

## 3. Preconditions For Future Rollback Execution

A future rollback execution prototype may only run if:

- Phase 2 acceptance decision is accepted
- sandbox path-safety verifier passes
- rollback artifact verifier passes
- target path is inside `examples/sandbox`
- pre-write snapshot exists
- snapshot hash matches
- explicit `ConfirmRollback` flag is supplied
- git working tree is clean

## 4. Proposed Future Rollback Flow

This is future-flow design only:

- load rollback artifact
- verify sandbox root
- verify target manifest is inside sandbox
- verify pre-write snapshot hash
- copy snapshot back over target manifest
- write rollback report
- verify restored hash
- fail closed if any check fails

## 5. Forbidden Future Rollback Targets

- MaxineShow project
- O3DE engine files
- O3DE project files outside `examples/sandbox`
- Asset Processor cache
- database files
- prefab publication targets
- entity spawn targets

## 6. Required Future Rollback Command Shape

Future command shape:

`Invoke-MaxineSandboxRollback.ps1 -RollbackArtifactPath <path> -ConfirmRollback`

This command is not implemented in this planning phase.

## 7. Required Future Rollback Report Fields

- rollback_id
- sandbox_id
- target_manifest_copy
- restored_from_snapshot
- pre_restore_hash
- post_restore_hash
- status
- restored_at_utc
- operator
- safety

## 8. Phase Verdict

This phase authorizes rollback execution planning only. It does not authorize rollback execution, sandbox writes, authoritative writes, product resolution, or Asset ID claims.
