# Editor Smoke Stall Diagnostics

The gated Editor smoke supports split live diagnostic modes so a private runner can isolate stalls without broadening publication or packaging authority.

Run modes in order:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode hello --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode product-evidence --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode temp-level --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode entity-minimal --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode full --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Stop at the first failing or stalled mode. Each run writes `progress.jsonl` beside `editor_smoke_live_report.json`, `stdout.txt`, and `stderr.txt`.

The PR #116 blocker was classified as `idle_wait_stall`: `create_level_no_prompt` returned, the approved temp level was written under `Levels/_maxine_smoke`, and then `azlmbr.legacy.general.idle_wait_frames(5)` did not return while the Editor log was loading the temp map. The smoke skips that idle wait by default and records `idle_wait_skipped`. Set `MAXINE_EDITOR_SMOKE_ENABLE_IDLE_WAIT=1` only to reproduce or diagnose the old path.

Expected safety posture is unchanged:

- `live_publication=false`
- `release_packaging=false`
- `production_level_mutation=false`
- no Asset Cache deletion
- no production levels
- no external service calls
- no fake pass on timeout, missing report, or nonzero Editor exit

The first fixed full pass is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```
