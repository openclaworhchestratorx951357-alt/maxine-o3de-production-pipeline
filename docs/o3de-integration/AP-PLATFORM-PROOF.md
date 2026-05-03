# AP Platform Proof

Platform proof is a read-only evidence layer that evaluates whether candidate product and job evidence suggests a platform alignment with an intended target platform.

## What Platform Proof Means

Platform proof asks whether available evidence is consistent with a target platform contract.

It does not resolve products and it does not assert authoritative O3DE product identity.

## Why Product File Existence Is Not Enough

- files can exist for the wrong platform
- files can be stale while still present on disk
- row sampling can show candidate records without proving current platform correctness
- platform must be checked across product paths, job rows, and candidate row metadata

## Candidate Platform Evidence Sources

- product path segments such as `pc`, `windows`, `android`, `ios`, `linux`, `mac`
- job row platform/status columns
- product row platform columns
- file-validation path evidence (`normalized_path`, `resolved_path`, and safe-root context)

## Required Future Platform Proof Contract

- target platform declared by job/manifest
- candidate product platform matches target platform
- job platform matches target platform if present

## Forbidden Conclusions From Platform Proof Alone

- no product resolution
- no Asset ID claims
- no publication readiness from platform proof alone
