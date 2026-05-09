# First Live APB-Only Golden Corpus Run

This slice wires the first controlled live Asset Processor Batch path for a private self-hosted Windows runner. Normal CI remains fixture-backed and offline.

APB-only means:

- Asset Processor Batch may run only when every gate is explicit.
- O3DE Editor does not run.
- Editor Python smoke does not run.
- release packaging and publication do not run.
- production levels are not mutated.

## Required Environment

Set these on the private runner:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\MAXINE_GoldenCorpus"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
```

`O3DE_PROJECT_PATH\project.json` must contain the project name declared by the golden fixture.

## Commands

Default offline validation:

```powershell
python tools/validation/validate_all.py
```

Private runner dry-run checklist:

```powershell
python tools/ci/private_runner_apb_dry_run_checklist.py
```

APB readiness without execution:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness
```

APB-only live non-strict:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
```

APB-only live strict:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

Private runner suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

## Outputs

Live APB command outputs are written under:

```text
artifacts/o3de-integration/apb/
```

Reports record command argv, working directory, exit code, stdout/stderr refs, APB report ref, golden project fixture ref, runner context, and safety flags. Generated live artifacts are not committed by default.

Skipped/unavailable is not pass. Live APB success is not production publication and is not Editor/runtime success.

## 2026-05-09 Attempt Notes

Local discovery found:

- engine root: `C:\src\o3de`
- controlled golden project: `%USERPROFILE%\O3DE\Projects\MAXINE_GoldenCorpus`
- APB executable used for the attempt: `%USERPROFILE%\O3DE\Projects\_archive\RemoteControlHost-2026-04-20\build\windows\bin\profile\AssetProcessorBatch.exe`

Readiness and fixture validation passed before live execution. The live APB command started but did not complete within the local timeout window; the APB process was stopped and the run is recorded as stalled, not passed. The generated attempt directory contained empty stdout/stderr files and no completed APB report.

Safety outcome:

- live Editor execution: false
- live publication: false
- release packaging: false
- production level mutation: false
- Asset Cache deletion: false
- project source deletion: false

Follow-up before retrying live APB:

- run APB from a build paired with the controlled golden project when available
- keep fixture mode offline even when live gates exist in the parent environment
- do not substitute `AssetProcessor.exe` for `AssetProcessorBatch.exe`
