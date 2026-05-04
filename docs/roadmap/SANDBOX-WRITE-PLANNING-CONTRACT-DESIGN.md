# Sandbox Write Planning Contract Design

## 1. Purpose

This document defines the planning contract for a future sandbox-only write prototype.

## 2. Non-goals

- sandbox writes are not implemented
- rollback execution is not implemented
- authoritative writes are not implemented
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs
- no production project mutation is allowed

## 3. Dependency On Rollback Execution Design

Sandbox write planning depends on:

- Phase 2 accepted decision
- sandbox fixture path-safety design
- sandbox rollback artifact design
- sandbox rollback execution design
- rollback command still absent
- sandbox write command still absent

## 4. Future Sandbox Write Planning Scope

Future planning may describe, but not execute:

- copying a fixture manifest into `examples/sandbox/manifests/working`
- proposing sandbox-only field changes
- proposing rollback metadata
- proposing `proof_refs`
- proposing a temporary `sandbox_only` resolution marker
- never writing real Asset IDs
- never publishing prefabs
- never spawning entities
- never touching real O3DE project files

## 5. Required Future Preconditions Before Any Sandbox Write Prototype Implementation

A future implementation branch may only be considered if:

- sandbox path-safety verifier passes
- rollback artifact verifier passes
- rollback execution design verifier passes
- target manifest is inside `examples/sandbox`
- target manifest is a copy, not source of truth
- pre-write snapshot exists
- approval artifact exists
- execution gate policy exists
- git working tree is clean
- explicit `ConfirmSandboxWrite` flag is supplied

## 6. Proposed Future Sandbox Write Command Shape

Future command shape:

`Invoke-MaxineSandboxResolverWrite.ps1 -SandboxWritePlanPath <path> -ConfirmSandboxWrite`

This command is not implemented in this planning phase.

## 7. Required Future Sandbox Write Report Fields

- sandbox_write_id
- sandbox_id
- target_manifest_copy
- pre_write_snapshot
- proposed_changes
- applied_changes
- rollback_artifact
- rollback_verification_ref
- status
- operator
- safety

## 8. Forbidden Future Write Targets

- MaxineShow project
- O3DE engine files
- O3DE project files outside `examples/sandbox`
- Asset Processor cache
- database files
- prefab publication targets
- entity spawn targets
- real product resolution records
- real Asset IDs

## 9. Phase Verdict

This phase authorizes sandbox write planning only. It does not authorize sandbox write implementation, rollback execution, authoritative writes, product resolution, or Asset ID claims.
