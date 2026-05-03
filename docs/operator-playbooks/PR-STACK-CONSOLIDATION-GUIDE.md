# PR Stack Consolidation Guide

## Purpose

This playbook documents how to consolidate the intentionally chained resolver ladder PR stack safely.

## Consolidation Policy

- The current stack is intentionally chained and should be merged in order.
- Recommended merge order is PR #1 through PR #20.
- After each merge, rebase or retarget the next PR if GitHub does not auto-update base references.
- Do not squash unrelated proof contracts together unless you are intentionally creating a consolidated history.
- Verify CI after each merge.
- If conflicts happen, prefer the newer safety language from later PRs.
- Do not merge write-capable implementation because none should exist in this stack.

## Recommended Merge Order

1. PR #1 `codex/manifest-first-adapter -> main`
2. PR #2 `codex/asset-resolver-poc -> codex/manifest-first-adapter`
3. PR #3 `codex/o3de-ap-query-adapter -> codex/asset-resolver-poc`
4. PR #4 `codex/ap-metadata-discovery -> codex/o3de-ap-query-adapter`
5. PR #5 `codex/ap-db-schema-inspection -> codex/ap-metadata-discovery`
6. PR #6 `codex/ap-source-product-row-map -> codex/ap-db-schema-inspection`
7. PR #7 `codex/ap-source-identity-match -> codex/ap-source-product-row-map`
8. PR #8 `codex/ap-candidate-product-match -> codex/ap-source-identity-match`
9. PR #9 `codex/ap-product-file-existence -> codex/ap-candidate-product-match`
10. PR #10 `codex/ap-resolver-readiness-gate -> codex/ap-product-file-existence`
11. PR #11 `codex/authoritative-resolver-dry-run-contract -> codex/ap-resolver-readiness-gate`
12. PR #12 `codex/ap-job-state-proof -> codex/authoritative-resolver-dry-run-contract`
13. PR #13 `codex/ap-platform-proof -> codex/ap-job-state-proof`
14. PR #14 `codex/ap-product-freshness-proof -> codex/ap-platform-proof`
15. PR #15 `codex/ap-product-identity-proof -> codex/ap-product-freshness-proof`
16. PR #16 `codex/update-authoritative-planner-proof-stack -> codex/ap-product-identity-proof`
17. PR #17 `codex/authoritative-write-protocol-proposal -> codex/update-authoritative-planner-proof-stack`
18. PR #18 `codex/operator-approval-validation -> codex/authoritative-write-protocol-proposal`
19. PR #19 `codex/approved-write-dry-run-report -> codex/operator-approval-validation`
20. PR #20 `codex/final-execution-gate-policy -> codex/approved-write-dry-run-report`

## Per-PR Checklist

Use this checklist for each PR in the stack:

- PR title confirmed
- base branch confirmed
- head branch confirmed
- CI status green
- merge result recorded
- next PR retargeted/rebased if needed

## Suggested Tracking Template

| PR | Title | Base Branch | Head Branch | CI Status | Merge Result | Next PR Retargeted |
| --- | --- | --- | --- | --- | --- | --- |
| #1 |  |  |  |  |  |  |
| #2 |  |  |  |  |  |  |
| #3 |  |  |  |  |  |  |
| #4 |  |  |  |  |  |  |
| #5 |  |  |  |  |  |  |
| #6 |  |  |  |  |  |  |
| #7 |  |  |  |  |  |  |
| #8 |  |  |  |  |  |  |
| #9 |  |  |  |  |  |  |
| #10 |  |  |  |  |  |  |
| #11 |  |  |  |  |  |  |
| #12 |  |  |  |  |  |  |
| #13 |  |  |  |  |  |  |
| #14 |  |  |  |  |  |  |
| #15 |  |  |  |  |  |  |
| #16 |  |  |  |  |  |  |
| #17 |  |  |  |  |  |  |
| #18 |  |  |  |  |  |  |
| #19 |  |  |  |  |  |  |
| #20 |  |  |  |  |  |  |
