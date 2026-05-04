# Sandbox Writer Skeleton Implementation Note

This slice adds a real, locked sandbox writer skeleton and a paired rollback skeleton for generated resolver placeholder artifacts.

## Commands
- `scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1`
- `scripts/powershell/Invoke-MaxineSandboxRollback.ps1`

## What This Implementation Does
- Accepts a structured write plan JSON.
- Validates required plan schema fields.
- Requires explicit sandbox scope and explicit sandbox approval.
- Restricts all writes to `examples/sandbox/staging` only.
- Emits a machine-readable write receipt with pre/post SHA-256 values.
- Allows rollback only for files listed in the receipt and only under the approved sandbox root.

## What This Implementation Explicitly Does Not Do
- No authoritative writes.
- No sandbox write to production paths.
- No O3DE Editor execution.
- No Asset Processor execution.
- No product resolution or Asset ID claims.
- No spawn/publish operations.
