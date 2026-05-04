# Sandbox Writer Skeleton Implementation Note

This slice adds a real, locked sandbox writer skeleton and a paired rollback skeleton for generated resolver placeholder artifacts.

## Commands
- `scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1`
- `scripts/powershell/Invoke-MaxineSandboxRollback.ps1`
- `scripts/powershell/Invoke-MaxineSandboxReceiptInspect.ps1`
- `scripts/powershell/Invoke-MaxineSandboxReviewPacketBuild.ps1`
- `scripts/powershell/Invoke-MaxineSandboxReviewPacketInspect.ps1`
- `scripts/powershell/Invoke-MaxineSandboxReviewDecisionRecord.ps1`
- `scripts/powershell/Invoke-MaxineSandboxReviewDecisionInspect.ps1`
- `scripts/powershell/Invoke-MaxineSandboxWorkflowRun.ps1`
- `scripts/powershell/Invoke-MaxineSandboxWorkflowInspect.ps1`
- `scripts/powershell/Invoke-MaxineSandboxEvidenceBundleExport.ps1`
- `scripts/powershell/Invoke-MaxineSandboxOperatorSummary.ps1`
- `scripts/powershell/Invoke-MaxineProjectInventoryRead.ps1`
- `scripts/powershell/Invoke-MaxineProjectInventoryInspect.ps1`

## What This Implementation Does
- Accepts a structured write plan JSON.
- Validates required plan schema fields.
- Requires explicit sandbox scope and explicit sandbox approval.
- Restricts all writes to `examples/sandbox/staging` only.
- Emits a machine-readable write receipt with pre/post SHA-256 values.
- Records each write/blocked outcome in `examples/sandbox/receipts/index.json`.
- Preserves receipt history and updates status to `rolled_back` on successful rollback.
- Supports read-only receipt inspection by list and `receipt_id`.
- Builds sandbox-only review packets from receipts under `examples/sandbox/review-packets`.
- Supports read-only review packet inspection by list and `review_packet_id`.
- Records sandbox-only review decisions under `examples/sandbox/review-decisions`.
- Supports read-only review decision inspection by list and `decision_id`.
- Records rollback requests as intent only (`requested_next_action=rollback_requested`) without auto-executing rollback.
- Runs end-to-end sandbox workflow modes (WriteOnly, WriteAndReview, WriteReviewAndDecision, RollbackRequestedOnly) and writes workflow records under `examples/sandbox/workflow-runs`.
- Supports read-only workflow inspection by list and `workflow_run_id`.
- Exports sandbox-local evidence bundles under `examples/sandbox/evidence-bundles` with copied JSON snapshots for workflow/receipt/review/decision metadata.
- Provides operator summary output with read-only default behavior and optional sandbox-local report output under `examples/sandbox/operator-reports`.
- Adds read-only project awareness inventory scanning with sandbox-local output under `examples/sandbox/project-inventory`.
- Enforces capability-state boundaries via `examples/capabilities/maxine-capability-matrix.json`.
- Allows rollback only for files listed in the receipt and only under the approved sandbox root.

## What This Implementation Explicitly Does Not Do
- No authoritative writes.
- No sandbox write to production paths.
- No O3DE Editor execution.
- No Asset Processor execution.
- No product resolution or Asset ID claims.
- No spawn/publish operations.
