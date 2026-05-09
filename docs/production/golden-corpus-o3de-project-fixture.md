# Golden Corpus O3DE Project Fixture

This fixture contract defines how future private-runner O3DE checks should map MAXINE manifests, source assets, expected products, temporary levels, logs, screenshots, and retained evidence into a controlled local project.

It is fixture-only by default. It does not create an O3DE project, run Asset Processor Batch, run Editor, mutate levels, publish, or download assets.

## What It Validates

The contract lives at:

```text
examples/o3de-golden-project/maxine-golden-project.fixture.json
```

It validates:

- project-relative allowed roots
- forbidden production, engine, registry, and cache roots
- source layout roots for characters, packages, prefabs, motions, materials, colliders, and temp content
- temp level policy under `Levels/_maxine_smoke`
- evidence/artifact roots under `Saved/MaxineEvidence`, `Saved/Logs/Maxine`, and `Saved/Screenshots/Maxine`
- product expectations by lane
- resolver, Asset Processor Batch, Editor smoke, QC, evidence bundle, package/prefab, undo, and cleanup references
- release cache-heuristic rejection

## Commands

Default offline validation:

```powershell
python tools/validation/validate_all.py
```

Direct fixture validation:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
```

Local readiness without mutation:

```powershell
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
```

Strict local readiness:

```powershell
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness --strict
```

When local O3DE project/tooling paths are unavailable, non-strict readiness reports `skipped` with `MXN_VALIDATION_TOOL_UNAVAILABLE`. Strict readiness fails with the same code. Skipped readiness is not pass.

## Temp Level Policy

Future Editor smoke should use only sandbox levels under:

```text
Levels/_maxine_smoke/
```

Generated or temporary project content belongs under:

```text
Assets/_maxine_smoke/
```

Evidence and retained artifacts belong under:

```text
Saved/MaxineEvidence/
Saved/Logs/Maxine/
Saved/Screenshots/Maxine/
```

Production levels are forbidden by default. Cleanup remains dry-run only in this slice; any future live cleanup must be scoped to declared temp roots and recorded in the undo/cleanup evidence.

## Private Runner Prep

The private Windows runner should validate the golden project fixture before APB or Editor commands. Required local environment variables remain:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\maxine-project"
$env:O3DE_EDITOR_EXECUTABLE = "C:\path\to\Editor.exe"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
```

Live O3DE/APB/Editor execution remains opt-in and private-runner-only. This contract prepares the project layout and evidence retention rules; it still does not prove live Editor/runtime gameplay readiness.
