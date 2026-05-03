# AP Product Freshness Proof

Product freshness proof is a read-only evidence layer that checks whether candidate product timestamps appear current relative to source timestamps.

## What Product Freshness Proof Means

Freshness proof evaluates timestamp evidence to determine whether candidate products are likely newer than, or at least not older than, their source evidence.

It does not resolve products and it does not claim authoritative Asset IDs.

## Why File Existence and Platform Proof Are Still Insufficient

- files can exist but be stale
- platform hints can match while product outputs are outdated
- row samples can point to candidate products without proving recency
- freshness requires explicit source/product/job timestamp comparison evidence

## Candidate Freshness Evidence Sources

- product file `modified_utc` from file validation evidence
- source file `modified_utc` from filesystem probe evidence
- job-state timestamp fields
- source/product row timestamp fields

## Required Future Freshness Proof Contract

- source timestamp known
- product timestamp known
- product timestamp is not older than source timestamp
- job timestamp/status supports the candidate product

## Forbidden Conclusions From Freshness Proof Alone

- no product resolution
- no Asset ID claims
- no publication readiness from freshness proof alone
