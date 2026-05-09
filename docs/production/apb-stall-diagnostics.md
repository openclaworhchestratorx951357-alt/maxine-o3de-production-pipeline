# APB Stall Diagnostics

This diagnostic slice investigates `AssetProcessorBatch.exe` candidates before any full live golden corpus retry.

It does not run O3DE Editor, Editor smoke, release packaging, publication, cache deletion, or source-asset deletion.

## Why Provenance Matters

`AssetProcessorBatch.exe` must be paired with the selected engine and controlled project. An archived binary from another project can load different settings, gems, cache state, or build products.

Do not substitute:

- `AssetProcessor.exe`
- renamed tools
- archived APB binaries whose nearby `project.json` does not match `MAXINE_GoldenCorpus`
- binaries without a clear engine/build/install path

## Diagnostic Commands

Inventory candidates:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory
```

Inventory a selected setup:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
```

Run bounded diagnostics against a candidate:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --run-bounded-diagnostics --timeout-seconds 120 --candidate "<path-to-AssetProcessorBatch.exe>" --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
```

Every bounded command captures stdout/stderr, records duration and exit/timeout state, and attempts process-tree cleanup on timeout. A stalled diagnostic is recorded as `MXN_APB_DIAGNOSTIC_STALLED`; it is never treated as a pass.

## 2026-05-09 Result

Local inventory found no project-paired APB for `MAXINE_GoldenCorpus`.

The only discovered `AssetProcessorBatch.exe` was:

```text
%USERPROFILE%\O3DE\Projects\_archive\RemoteControlHost-2026-04-20\build\windows\bin\profile\AssetProcessorBatch.exe
```

That binary is rejected for live APB success because its nearby project is `RemoteControlHost`, not `MAXINE_GoldenCorpus`.

A bounded help-like diagnostic against that binary stalled for 120 seconds. Captured output showed repeated Terrain dependency warnings involving `C:\src\o3de\Gems\Terrain\Assets\Shaders\Terrain\SceneSrg.azsli`. The process tree was stopped after timeout. No full live APB retry was run.

## Next Setup Action

Produce or provide an `AssetProcessorBatch.exe` paired with `C:\src\o3de` and `%USERPROFILE%\O3DE\Projects\MAXINE_GoldenCorpus`, then rerun:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
python tools/o3de/diagnose_asset_processor_batch.py --run-bounded-diagnostics --timeout-seconds 120 --candidate "<project-paired AssetProcessorBatch.exe>" --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
```

Only after inventory and bounded diagnostics pass should the next slice attempt a single bounded full live APB-only golden corpus run.
