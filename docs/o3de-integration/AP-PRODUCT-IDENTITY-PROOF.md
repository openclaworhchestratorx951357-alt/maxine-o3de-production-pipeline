# AP Product Identity Proof

## Purpose

AP product identity proof defines a read-only evidence contract for determining whether a candidate product appears to match the intended source and expected product contract.

This proof is non-authoritative. It does not resolve products and does not permit write-capable resolver actions.

## Why This Proof Is Needed

Product type, file existence, and freshness are still insufficient by themselves:

- a correct extension can still belong to the wrong source
- an existing file can be stale, unrelated, or from a different platform/job
- freshness signals can exist without a trustworthy source-to-product link

## Required Identity Evidence

All of the following evidence dimensions are required for candidate product identity support:

- source identity candidate match
- expected product contract match
- product candidate row match
- product file existence match
- job-state support
- platform support
- freshness support

## Forbidden Conclusions

Product identity proof alone must not be used to conclude any of the following:

- no product resolution
- no Asset ID claims
- no prefab publication
- no entity spawning
