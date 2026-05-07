# Natural Language O3DE Command Pack Boundary v1

## Purpose
This hardening layer supersedes the unsafe early PR #92 path as the merge-safe static command-envelope boundary for natural-language O3DE requests. PR #92 remains unmerged and unapproved until it is revised or closed against this contract.

The only admitted behavior in this slice is static compilation and static validation:

```text
natural-language request -> static command envelope -> static validator -> blocked or evidence-only report
```

No command envelope performs work in O3DE. No command envelope admits work in O3DE.

## Explicit Non-Claims
This command pack is:

- not a runner implementation
- not runner admission
- not command admission
- not direct O3DE execution
- not Editor or runtime execution
- not Asset Processor execution
- not Blender or DCC execution
- not Gem adapter implementation
- not MaxineAgentControl Gem implementation
- not publication
- not production-ready

The compiler and validator only produce or inspect static JSON envelopes. They do not call O3DE, the Editor, Asset Processor, Blender, DCC tools, runners, Gem adapters, publication paths, spawn paths, Cache/live DBs, production paths, or engine write paths.

## Required Gate Chain
Any future execution-requiring command is blocked unless a later, separate slice supplies candidate-specific admission and proves all of these gates:

- candidate-specific admission
- runner interface contract
- sandbox boundary contract
- receipt contract
- safety verifier
- proof flow

A natural-language command envelope cannot bypass runner interface validation. It cannot bypass sandbox boundary validation. It cannot bypass receipt contract validation. It cannot bypass approval or admission gates.

## Status Fields
Every envelope carries explicit status fields:

- `command_envelope_status`
- `command_admission_status`
- `runner_required`
- `runner_interface_required`
- `runner_implemented`
- `runner_admitted`
- `execution_admitted`
- `publication_admitted`
- `production_ready_claimed`
- `sandbox_boundary_required`
- `sandbox_boundary_validation_required`
- `receipt_contract_required`
- `approval_required`
- `approval_phrase_present`
- `refusal_reason_code` when blocked

For this slice, `runner_implemented`, `runner_admitted`, `execution_admitted`, `publication_admitted`, `production_ready_claimed`, and `approval_phrase_present` must remain `false`.

## Output Boundary
Compiler output paths are fail-closed and sandbox-only. The compiler rejects:

- parent traversal
- absolute paths
- network paths
- symlink or junction escape through canonical path validation
- engine path writes
- production path writes
- Cache/live DB writes
- publish/export writes
- spawn output paths
- executable, binary, asset, archive, database, and cache extensions

Allowed output extensions are `.json`, `.md`, `.txt`, and `.sha256` under approved `examples/sandbox/` roots only.

## Relationship To PR #92
PR #92 introduced useful static pieces, but its boundaries were too early for the post-PR93 chain. This PR supersedes that path with a hardened static layer:

- full post-PR93 source references are required
- non-read-only commands are blocked
- runner interface, sandbox boundary, and receipt contract gates are explicit
- output paths fail closed to sandbox-only locations
- unsafe and unimplemented modes are rejected
- direct O3DE control and Gem adapter work remain separate future work

Recommended follow-up: close PR #92 as superseded or revise it to match this hardening layer before reconsidering merge.
