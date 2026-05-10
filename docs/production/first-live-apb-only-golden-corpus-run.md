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

## Stall Diagnostic Follow-Up

The follow-up diagnostic slice adds:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory
python tools/o3de/diagnose_asset_processor_batch.py --run-bounded-diagnostics --timeout-seconds 120 --candidate "<path-to-AssetProcessorBatch.exe>" --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
```

Inventory confirmed the RemoteControlHost APB is archived and project-mismatched. A bounded help-like diagnostic against it stalled and was cleaned up after timeout. The next live APB attempt should use a project-paired APB binary, not the archived RemoteControlHost binary.

## Project-Paired APB Build Status

The project-paired APB follow-up attempted to produce `C:\src\o3de\build\windows\bin\profile\AssetProcessorBatch.exe` with a single-process profile build. The build progressed without a new C1060 during the bounded window but did not finish producing APB, so it was stopped and no full live golden corpus APB retry was attempted.

Before retrying the full APB-only run, one of these must be true:

- the `AssetProcessorBatch` target finishes in the `C:\src\o3de` build and diagnostic inventory selects it, or
- a prebuilt APB paired with `C:\src\o3de` and `MAXINE_GoldenCorpus` is provided and bounded diagnostics pass.

## Build Environment Completion Status

The APB build-environment follow-up completed the `AssetProcessorBatch` target from `C:\src\o3de\build\windows` using a low-memory Visual Studio profile build:

```powershell
$env:CL = "/Zm200"
cmake --build C:\src\o3de\build\windows --target AssetProcessorBatch --config profile --parallel 1 -- /m:1 /nodeReuse:false /p:CL_MPCount=1 /p:UseMultiToolTask=false /v:m
```

Produced APB:

```text
C:\src\o3de\build\windows\bin\profile\AssetProcessorBatch.exe
```

Diagnostics now show:

- build environment: pass
- APB inventory: selected engine-paired APB under `C:\src\o3de`
- RemoteControlHost APB: still rejected for `MAXINE_GoldenCorpus`
- `AssetProcessor.exe`: still rejected as a substitute
- bounded APB diagnostics: completed without stall
- APB readiness: pass
- live APB execution: false
- live Editor execution: false
- live publication: false

The help-like APB diagnostic returns nonzero because APB does not behave like a normal CLI help command in this context; the diagnostic records that as a responsive, non-blocking probe, not as full APB success. The next slice should perform the first bounded full APB-only golden corpus retry with the produced engine-paired APB.

## First Full APB-Only Run Result

The first full APB-only golden corpus retry used the project/engine-paired APB:

```text
C:\src\o3de\build\windows\bin\profile\AssetProcessorBatch.exe
```

Command:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

The wrapper set an explicit timeout through `MAXINE_APB_TIMEOUT_SECONDS=1800`. APB started, processed the controlled `MAXINE_GoldenCorpus` project, exited `0`, and did not time out. The APB-only integration suite then invoked the same APB path and also reached APB execution.

The run is still recorded as `fail`, not pass, because post-run Asset Processor database evidence did not satisfy the golden corpus product contract:

- produced: `azmodel`, `procprefab`, `azmaterial`
- missing: `actor`, `motion`, `motionset`, `animgraph`, `pxmesh`
- error: `MXN_ASSET_PRODUCT_MISSING`
- cache heuristic used: false

APB exit `0` means the batch processor completed its work queue. It does not prove the golden corpus release products exist. The wrapper now records missing expected products from Asset Processor database evidence and fails closed when release/product expectations are absent.

Safety outcome:

- live Asset Processor Batch execution: true
- live Editor execution: false
- live publication: false
- release packaging: false
- Asset Cache deletion: false
- project source deletion: false
- production mutation: false

Sanitized evidence:

```text
examples/private-runner/apb-live-full-golden-corpus.failed.example.json
```

Raw local logs and live reports remain under:

```text
artifacts/o3de-integration/apb/
```

Next action: configure or add the controlled golden corpus source assets/gems/settings needed to produce `actor`, `motion`, `motionset`, `animgraph`, and `pxmesh`, then rerun the bounded APB-only command.

## Release-Rigged Product Evidence Follow-Up

The release-rigged product evidence follow-up staged controlled local source fixtures in:

```text
%USERPROFILE%\O3DE\Projects\MAXINE_GoldenCorpus\Assets\Characters\MAXINE\release
```

The staged sources came from the local O3DE source tree only:

- Jack actor scene source and actor scene settings for `actor`
- Jack animation scene source and motion scene settings for `motion`
- EMotionFX test `motionset` and `animgraph` source artifacts
- O3DE AutomatedTesting PhysX collider scene source/settings for the remaining `pxmesh` investigation

The follow-up also built the narrow PhysX editor module target:

```powershell
cmake --build C:\src\o3de\build\windows --target PhysX5.Editor --config profile --parallel 1 -- /m:1 /nodeReuse:false /p:CL_MPCount=1 /p:UseMultiToolTask=false /v:m
```

`C:\src\o3de\build\windows\bin\profile\PhysX5.Editor.Gem.dll` was produced with no C1060. The controlled project was updated locally with `PhysXCommon`, `LmbrCentral`, and `CommonFeaturesAtom` through the O3DE CLI.

The APB-only command and APB-only suite were rerun. APB exited `0`, did not stall, and produced:

- `azmodel`
- `actor`
- `procprefab`
- `motion`
- `motionset`
- `animgraph`
- `azmaterial`

The run still fails closed because `pxmesh` remains missing from Asset Processor database product evidence. `cache_heuristic_used=false`; no cache heuristic is accepted as release proof.

Sanitized evidence:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.missing-products.example.json
```

The source audit can be run without live O3DE execution:

```powershell
python tools/o3de/audit_golden_corpus_sources.py --corpus examples/golden-corpus --project %USERPROFILE%\O3DE\Projects\MAXINE_GoldenCorpus --json
```

Next action: diagnose why the PhysX mesh exporter does not emit `.pxmesh` for the controlled project under APB, or add an explicit collider waiver policy only if the release fixture is intentionally reclassified as not physics-enabled.

## Pxmesh Resolution Follow-Up

The pxmesh resolution follow-up reconfigured the local `C:\src\o3de\build\windows` tree with the controlled project in `LY_PROJECTS`, which generated project-specific APB/AssetBuilder registry files for `MAXINE_GoldenCorpus`. Those registry files include the PhysX editor module.

APB-only processing was rerun with:

```text
C:\src\o3de\build\windows\bin\profile\AssetProcessorBatch.exe
```

The controlled release-rigged product evidence now includes:

- `azmodel`
- `actor`
- `procprefab`
- `motion`
- `motionset`
- `animgraph`
- `pxmesh`
- `azmaterial`

The `.pxmesh` product is recorded as:

```text
pc/assets/characters/maxine/release/r0-b_body.fbx.pxmesh
```

It is tied to the controlled source:

```text
Assets/Characters/MAXINE/release/maxine_physx_final_spherebot.fbx
```

`missing_products=[]`, `pending_assets=[]`, and `cache_heuristic_used=false`.

The APB-only command and APB-only suite still fail closed because the APB process exits `1` on a non-golden engine/Gem asset:

```text
C:/src/o3de/Gems/DiffuseProbeGrid/Assets/Passes/DiffuseProbeGridQueryFullscreenWithAlbedo.pass
```

This is now classified as `MXN_APB_PROCESS_EXIT_NONZERO`, not as missing pxmesh and not as unavailable tooling. Live Editor execution and publication remain blocked.

Sanitized evidence:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.pxmesh-produced-apb-nonzero.example.json
```

The focused product evidence audit can be run with:

```powershell
python tools/o3de/audit_apb_product_evidence.py --project $env:O3DE_PROJECT_PATH --apb-report <asset_processor_batch_live_report.json> --apb-executable $env:ASSET_PROCESSOR_BATCH_EXECUTABLE --json
```

Next action: fix or safely scope the unrelated DiffuseProbeGrid APB process failure so APB exits `0` while preserving the resolved release-rigged product evidence.

## DiffuseProbeGrid Process Failure Follow-Up

The DiffuseProbeGrid follow-up reproduced the nonzero APB process exit and confirmed the failed source was outside the controlled golden corpus:

```text
C:/src/o3de/Gems/DiffuseProbeGrid/Assets/Passes/DiffuseProbeGridQueryFullscreenWithAlbedo.pass
```

Root cause classification: project Gem enablement. `DiffuseProbeGrid` was directly enabled in the controlled `MAXINE_GoldenCorpus` project, but the release-rigged character APB evidence does not require diffuse probe grid assets. APB therefore scanned a non-golden engine Gem pass asset and failed during pass asset job creation.

The controlled project was fixed by disabling only `DiffuseProbeGrid` with the O3DE CLI, then regenerating the project-specific CMake registry metadata for `C:\src\o3de\build\windows`. No O3DE engine source asset was patched, no APB process failure was suppressed, and no APB wrapper scoping change was needed.

After the fix:

- APB process exit code: `0`
- wrapper exit code: `0`
- APB-only suite exit code: `0`
- product matrix status: `pass`
- produced products: `azmodel`, `actor`, `procprefab`, `motion`, `motionset`, `animgraph`, `pxmesh`, `azmaterial`
- missing products: none
- pending products: none
- `cache_heuristic_used=false`
- `live_asset_processor_batch_execution=true`
- `live_editor_execution=false`
- `live_publication=false`
- `release_packaging=false`

Sanitized evidence:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.apb-clean.pass.example.json
docs/production/diffuseprobegrid-apb-process-failure.md
```

Next action: prepare gated live Editor smoke on the private runner, still non-publishing and with release packaging disabled.
