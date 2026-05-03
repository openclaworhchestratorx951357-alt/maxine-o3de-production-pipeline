# AP Job-State Proof

AP job-state proof is a read-only evidence layer that extracts candidate job/status/result information from existing manifest row-mapping evidence.

It exists to answer one question:
Can we prove that candidate source/product rows are associated with plausible Asset Processor job-state evidence?

## Why Row Presence and File Existence Are Not Enough

- source/product rows can be stale snapshots
- product files can exist even if current AP jobs failed
- row and file evidence alone do not prove successful or current job-state
- authoritative resolution requires job-state context before any future resolved-write behavior

## Required Future Proof Fields

- source row link
- product row link
- job row link
- job status/result
- job platform if present
- timestamp/freshness indicators if present

## Forbidden Conclusions From Job-State Proof Alone

- no product resolution
- no Asset ID claims
- no publication readiness from job-state alone
