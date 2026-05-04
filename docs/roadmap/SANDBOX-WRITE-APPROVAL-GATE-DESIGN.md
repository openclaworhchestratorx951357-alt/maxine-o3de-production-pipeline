# Sandbox Write Approval Gate Contract Design

## 1. Purpose

This document defines an approval gate for a future sandbox-only write attempt after a dry-run report is ready.

## 2. Non-goals

- sandbox writes are not implemented
- rollback execution is not implemented
- authoritative writes are not implemented
- approval gate does not mutate manifests
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs
- no production project mutation is allowed

## 3. Dependency Stack

The approval gate depends on:

- Phase 2 accepted decision
- sandbox write plan verifier
- sandbox write planning contract verifier
- sandbox write dry-run report verifier
- sandbox write dry-run contract verifier
- rollback execution design verifier
- path-safety verifier

## 4. Approval Gate Purpose

The approval gate should say whether a sandbox dry-run report is:

- approval_ready
- approval_blocked
- approval_incomplete

## 5. Required Approval Checks

- decision status accepted
- dry-run report status dry_run_ready
- dry-run report verifier passes
- operator approval artifact exists
- operator approval references dry-run report id
- approval scope is sandbox-only
- approval does not authorize implementation
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent

## 6. Required Future Validation Command Shape

Future command shape:

`Test-MaxineSandboxWriteApprovalGate.ps1 -DryRunReportPath <path> -ApprovalPath <path>`

This command validates approval only. It does not execute sandbox writes.

## 7. Required Future Approval Gate Report Fields

- approval_gate_report_id
- dry_run_report_id
- sandbox_write_plan_id
- sandbox_id
- status
- approval_id
- approval_scope
- checks
- blockers
- warnings
- safety
- generated_at_utc

## 8. Phase Verdict

This phase authorizes sandbox write approval-gate validation only. It does not authorize sandbox write implementation, rollback execution, authoritative writes, product resolution, or Asset ID claims.
