# Phase 2 Sandbox Fixture Layout and Path-Safety Design

## 1. Purpose

This phase defines the sandbox fixture layout and path-safety validation required before any future sandbox-only write prototype can be considered.

## 2. Non-goals

This phase is design-only and non-executing.

- no sandbox writes are implemented
- no rollback execution is implemented
- no authoritative writes are implemented
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs
- no production project paths are allowed

## 3. Sandbox Root Policy

Future sandbox root:

`examples/sandbox/`

Rules:

- all future sandbox write targets must be under `examples/sandbox/`
- all generated fixture outputs must remain under `examples/sandbox/`
- no production paths are allowed
- no absolute paths are allowed in fixture examples unless marked rejected

## 4. Proposed Sandbox Fixture Layout

Proposed layout:

```text
examples/sandbox/
  README.md
  manifests/
    source/
    working/
    snapshots/
    proposed/
    rollback/
    reports/
  approvals/
  plans/
  proposals/
  policy/
  logs/
```

## 5. Path Safety Rules

Rules:

- normalized path must remain inside sandbox root
- parent traversal is rejected
- absolute paths are rejected unless explicitly classified as rejected evidence
- Windows drive paths are rejected
- UNC paths are rejected
- symlink traversal must be treated as unsafe in future implementation
- production path tokens are rejected, including:
  - `MaxineShow`
  - `O3DE/Projects`
  - `O3de_GEMS_Research/Projects`
  - `Engine`
  - `Cache`
  - `AssetProcessor`
  - `.o3de`

## 6. Future Stop Conditions

Stop immediately if:

- target path escapes sandbox root
- target path contains parent traversal
- target path is absolute
- target path contains production tokens
- required sandbox fixture folders are missing
- approval or rollback references point outside sandbox

## 7. Phase Verdict

Phase 2 sandbox fixture path-safety design remains non-executing. It defines isolation and path-safety acceptance criteria only and does not authorize sandbox writes.
