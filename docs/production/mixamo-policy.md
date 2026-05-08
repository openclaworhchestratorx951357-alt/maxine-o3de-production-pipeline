# Mixamo Optional Manual Policy

Mixamo is optional acceleration, not a system of record and not a required production dependency.

## Rules

- Do not call Mixamo, Adobe, or external services from local validators.
- `external_service_optional` must be `true`.
- Manual handoff uses `pending_manual` and `MXN_MIXAMO_PENDING_MANUAL`.
- Offline mode blocks automation attempts with `MXN_EXTERNAL_SERVICE_BLOCKED`.
- Outputs must be stored locally and hash-tracked before release.
- Release lanes still have to pass canonical skeleton, product, package, and QC gates.

An unresolved Mixamo handoff can validate as a manual checkpoint, but it cannot pass release publication.
