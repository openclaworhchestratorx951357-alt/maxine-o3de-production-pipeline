# Sandbox Execution Intent and Execution-Hold Contract Design

## 1. Purpose

This document defines the final design-only gate after final preflight, before any future implementation branch may exist.

## 2. Non-goals

- sandbox writes are not implemented
- rollback execution is not implemented
- authoritative writes are not implemented
- execution intent does not mutate manifests
- execution hold does not execute anything
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs
- no production project mutation is allowed

## 3. Dependency Stack

Execution intent depends on:

- Phase 2 accepted decision
- sandbox write plan verifier
- sandbox write dry-run report verifier
- sandbox write approval gate verifier
- sandbox write final preflight verifier
- rollback artifact verifier
- rollback execution design verifier
- path-safety verifier

## 4. Execution Intent Purpose

Execution intent should say whether the project is:

- intent_recorded
- intent_blocked
- intent_hold

## 5. Execution Hold Purpose

Execution hold should say:

- no execution implementation is authorized
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent
- implementation branch must not be created until a later explicit accepted implementation decision exists

## 6. Required Checks

- final preflight status preflight_ready
- operator intent artifact exists
- intent scope is sandbox_only_implementation_planning
- intent does not authorize implementation
- execution hold status is active
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent

## 7. Required Future Command Shape

Future validation command shape:

`Test-MaxineSandboxExecutionIntent.ps1 -FinalPreflightReportPath <path> -IntentPath <path> -ExecutionHoldPath <path>`

This command validates execution intent and hold status only. It does not execute sandbox writes.

## 8. Phase Verdict

This phase authorizes sandbox execution intent recording and execution-hold validation only. It does not authorize sandbox write implementation, rollback execution, authoritative writes, product resolution, or Asset ID claims.
