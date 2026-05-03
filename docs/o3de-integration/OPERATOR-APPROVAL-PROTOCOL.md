# Operator Approval Protocol

## Purpose

This protocol defines the explicit human/operator gate required before any future authoritative resolver write attempt.

Operator approval is mandatory even when a write proposal is in `approval_required` status.

## Approval Matching Rules

The approval artifact must match proposal identity and scope:

- `proposal_id` must match the proposal artifact
- `approved_plan_id` must match `source_plan_id` from the proposal
- `approval_scope` must be explicit and non-empty

## Required Approval Artifact Fields

The operator approval artifact must include:

- `approval_id`
- `proposal_id`
- `approved_by`
- `approved_at_utc`
- `approval_reason`
- `approved_plan_id`
- `approval_scope`
- `approved_write_fields`
- `expires_at_utc`

## Forbidden Behavior

Approval artifacts are policy evidence only and must remain read-only:

- approval cannot execute writes
- approval cannot mark products resolved
- approval cannot claim Asset IDs
- approval cannot spawn/publish

## Approval Validation Statuses

Approval validation reports use these statuses:

- `approval_valid`
- `approval_invalid`
- `approval_expired`
- `proposal_not_approvable`
