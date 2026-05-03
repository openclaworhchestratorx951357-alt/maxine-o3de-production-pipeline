# Authoritative Execution Gate Policy

## Purpose

This policy defines the final gate that must be satisfied before any future authoritative resolver write could be considered.

This slice is policy-only and read-only. No write-capable behavior is implemented here.

## Required Preconditions

All of the following must be true before a future write command is even considered:

- dry-run plan status is `dry_run_ready`
- write proposal status is `approval_required`
- approval validation status is `approval_valid`
- pre-write report status is `pre_write_ready`
- git working tree is clean
- protected-branch expectations are satisfied
- rollback artifact is prepared
- operator runs an explicit manual command

## Mandatory Manual Command Shape

Future execution must use this explicit operator command shape:

`Invoke-MaxineAuthoritativeResolverWrite.ps1 -ManifestPath <path> -PreWriteReportPath <path> -RollbackPlanPath <path> -OperatorApprovalId <id> -ConfirmWrite`

This command is **not implemented yet**.

## Rollback Artifact Requirements

Any future write-capable implementation must require a rollback artifact that includes:

- pre-write snapshot
- previous manifest copy
- list of fields to revert
- timestamp
- operator identity
- rollback command proposal

## Forbidden Until Implemented

- no resolved products
- no Asset IDs
- no prefab publication
- no entity spawn

## Non-Goal

This policy does not authorize execution. It defines the gate only.
