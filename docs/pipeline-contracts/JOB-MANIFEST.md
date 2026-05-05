# Job Manifest Contract

This pipeline is **manifest-first**. Every job is represented by a machine-readable manifest that is updated as the job progresses.

## Manifest Location

- Job artifact root: `evidence/jobs/<job_id>/`
- Canonical manifest path: `evidence/jobs/<job_id>/manifest.json`
- Legacy/adhoc manifests under `examples/manifests/` remain valid for fixtures and tooling compatibility.

## Required Top-Level Manifest Sections

Every manifest structure is expected to include these sections:

- `job`
- `identity`
- `inputs`
- `generation`
- `dcc_conform`
- `o3de`
- `qc`
- `runtime_validation`
- `evidence`
- `provenance`
- `undo`
- `cleanup`
- `manual_review`
- `errors`

## Manifest-First Rules

- A manifest is required for every job.
- Failed jobs must still emit a manifest.
- Pending/manual jobs must still emit a manifest.
- Evidence references and failure class data must be attached to the manifest, not only console logs.
- Writer/update adapters validate the manifest against `schemas/maxine_job_manifest.schema.json` after each write.
- Writes are atomic where practical (write temp file then move).

## Draft vs Release Requirements

- Draft jobs are allowed to use a lighter subset of fields in generation/runtime details.
- Release jobs require stricter and more complete fields, including canonical source identity, product resolution, QC gate outcomes, and rollback/cleanup data.

The contract is designed so automation, operators, and CI can evaluate a job state from the manifest alone.

## Statuses

- Canonical: `created`, `running`, `pass`, `warn`, `fail`, `pending_manual`, `cancelled`
- Legacy compatibility: `queued` is still accepted

## Failure Behavior

- `status=fail` always records at least one structured error object (`code`, `message`, `stage`).
- Failure manifests still include evidence references and cleanup path hints.
- `pending_manual` records `manual_review.required=true`, a reason, and `manual_review.review_state=pending`.

## Validator Dependency Note

- `tools/manifest-validator/validate_manifest.py` supports a fallback minimal-validation path when `jsonschema` is unavailable.
- CI now pins `jsonschema==4.23.0` for strict schema validation.
- TODO: add a lightweight developer dependency file (for example `requirements-dev.txt`) that pins `jsonschema` for local reproducible validation.
