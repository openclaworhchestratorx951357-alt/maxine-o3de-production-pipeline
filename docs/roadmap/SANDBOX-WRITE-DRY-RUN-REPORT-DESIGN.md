# Sandbox Write Dry-Run Report Contract Design

## 1. Purpose

This document defines a dry-run report contract for evaluating a sandbox write plan before any future sandbox write implementation exists.

## 2. Non-goals

- sandbox writes are not implemented
- rollback execution is not implemented
- authoritative writes are not implemented
- dry-run reporting does not mutate manifests
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs
- no production project mutation is allowed

## 3. Dependency Stack

The dry-run report depends on:

- Phase 2 accepted decision
- sandbox fixture path-safety verifier
- sandbox rollback artifact verifier
- sandbox rollback execution design verifier
- sandbox write plan verifier
- sandbox write planning contract verifier

## 4. Dry-Run Report Purpose

The dry-run report should say whether a sandbox write plan is:

- dry_run_ready
- dry_run_blocked
- dry_run_incomplete

## 5. Required Dry-Run Checks

- decision status accepted
- sandbox write plan valid
- target path inside sandbox
- proposed changes do not touch forbidden fields
- rollback artifact reference exists
- rollback artifact verifier passes
- rollback execution design verifier passes
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent

## 6. Required Future Command Shape

Future command shape:

`Test-MaxineSandboxWriteDryRun.ps1 -SandboxWritePlanPath <path>`

This command validates the dry-run report only. It does not execute sandbox writes.

## 7. Required Future Dry-Run Report Fields

- dry_run_report_id
- sandbox_write_plan_id
- sandbox_id
- status
- checks
- blockers
- warnings
- target_manifest_copy
- rollback_artifact
- proposed_changes_count
- forbidden_changes_count
- safety
- generated_at_utc

## 8. Phase Verdict

This phase authorizes sandbox write dry-run reporting only. It does not authorize sandbox write implementation, rollback execution, authoritative writes, product resolution, or Asset ID claims.
