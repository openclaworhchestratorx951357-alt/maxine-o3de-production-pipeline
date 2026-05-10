# Private Windows O3DE Integration Runner

This runner wiring is for future local O3DE integration checks on a trusted private Windows machine. It does not install, register, or configure a self-hosted runner, and it does not require a runner token.

The manual workflow is:

```text
.github/workflows/o3de-private-windows-integration.yml
```

It is `workflow_dispatch` only and targets:

```yaml
runs-on: [self-hosted, Windows, X64, o3de, maxine-private]
```

The workflow has no `push` or `pull_request` trigger. It requires the confirmation phrase:

```text
I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER
```

For an operator checklist before any APB live attempt, use:

```powershell
python tools/ci/private_runner_apb_dry_run_checklist.py
python tools/ci/private_runner_apb_dry_run_checklist.py --json
```

The environment template is:

```text
examples/private-runner/o3de-runner.env.example
```

That template contains no credentials, keeps Editor smoke disabled, and keeps live commands disabled for dry-run readiness.

A sample skipped/unavailable dry-run report is checked in at:

```text
examples/private-runner/apb-dry-run-checklist.unavailable.example.json
```

## Local Environment

Set these on the private runner before attempting integration mode:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\maxine-project"
$env:O3DE_EDITOR_EXECUTABLE = "C:\path\to\Editor.exe"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
```

Validate the golden project fixture before APB or Editor smoke commands:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
```

The fixture defines safe project roots, the `Levels/_maxine_smoke` temp-level policy, evidence/log/screenshot roots, and package/prefab proof requirements. It does not create or mutate a real project.

Integration gates:

```powershell
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ENABLE_O3DE_EDITOR_SMOKE = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_EDITOR_COMMANDS = "0"
$env:MAXINE_ALLOW_LIVE_PUBLICATION = "0"
$env:MAXINE_ENABLE_RELEASE_PACKAGING = "0"
```

`MAXINE_ALLOW_LIVE_O3DE_COMMANDS=1` is a hard runner signal. Live Editor smoke additionally requires `MAXINE_ALLOW_LIVE_EDITOR_COMMANDS=1`; keep it `0` for readiness-only checks. Publication and release packaging gates must stay `0`.

## Beginner Commands

Default offline validation:

```powershell
python tools/validation/validate_all.py
```

Runner readiness:

```powershell
python tools/ci/o3de_runner_readiness.py
python tools/ci/o3de_runner_readiness.py --strict
```

Suite dry-run/readiness only:

```powershell
python tools/ci/run_o3de_integration_suite.py --dry-run
```

Fixture suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --mode fixture
```

Gated local integration suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --strict-integration
```

APB-only live suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

Editor smoke readiness:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root $env:O3DE_ENGINE_ROOT --project $env:O3DE_PROJECT_PATH --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict
```

When using the produced paired Editor on the controlled runner, pass it explicitly:

```powershell
$env:O3DE_EDITOR_EXECUTABLE = "C:/src/o3de/build/windows/bin/profile/Editor.exe"
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable $env:O3DE_EDITOR_EXECUTABLE --strict --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --editor-executable $env:O3DE_EDITOR_EXECUTABLE --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Gated Editor smoke suite prep:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --include-editor-smoke --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --editor-smoke-manifest examples/manifests/release_rigged.pass.example.json --strict-integration
```

The manual workflow modes `apb_live_non_strict` and `apb_live_strict` set APB gates only. The modes `editor_smoke_readiness`, `editor_smoke_live_non_strict`, and `editor_smoke_live_strict` add Editor smoke readiness checks. Live Editor modes require both live gates, run the APB strict baseline first, keep publication and release packaging disabled, and fail closed if the paired Editor executable is unavailable or strict readiness regresses.

Skipped/unavailable is not pass. Strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE` when required local tools are missing.

This wiring does not publish, mutate production levels, contact external services, or claim production-ready completion.
