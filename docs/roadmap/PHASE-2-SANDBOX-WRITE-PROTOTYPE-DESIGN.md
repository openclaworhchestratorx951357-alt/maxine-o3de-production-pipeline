# Phase 2 Sandbox-Only Write Prototype Design

## 1. Purpose

Phase 2 is a design-only review for a future sandbox-only write prototype in the M.A.X.I.N.E. production-control repository.

This phase defines boundaries, acceptance criteria, and rollback expectations before any write-capable resolver work is considered.

## 2. Non-goals

- no writes are implemented in this phase
- no products are resolved
- no Asset IDs are claimed
- no O3DE Editor automation is run
- no Asset Processor execution is run
- no production project mutation is allowed

## 3. Required Acceptance Before Any Future Prototype

A future sandbox-only prototype may only be considered after:

- Phase 1 baseline is accepted
- execution gate policy is accepted
- rollback protocol is accepted
- sandbox target is isolated and disposable
- operator approval policy is accepted
- all tests pass from `main`

## 4. Sandbox-only Target Definition

Future sandbox target requirements:

- disposable test manifest
- disposable test project or fixture
- no real MaxineShow production project
- no real production O3DE asset cache
- no engine source mutation
- no external asset promotion

## 5. Proposed Future Write Scope

Possible future write scope is proposal-only:

- write to a copied manifest fixture
- set a temporary sandbox-only resolved flag
- write `proof_refs`
- write rollback metadata
- never write real Asset IDs unless mocked
- never publish prefab
- never spawn entity

## 6. Required Rollback Proof

A future write prototype must prove:

- pre-write manifest snapshot exists
- post-write manifest diff exists
- rollback can restore exact pre-write state
- rollback report is generated
- rollback is tested automatically
- no files outside sandbox were touched

## 7. Future Prototype Stop Conditions

Stop immediately if:

- target path is outside sandbox
- rollback artifact is missing
- approval is missing
- git working tree is dirty
- write command is invoked without explicit `ConfirmSandboxWrite`
- any production path is detected

## 8. Phase 2 Verdict

Phase 2 remains design-only. It does not authorize sandbox writes. It prepares the acceptance criteria for a future sandbox-only prototype.
