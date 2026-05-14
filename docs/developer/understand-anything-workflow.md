# Dev-Only Understand-Anything Workflow

This workflow is for human and Codex comprehension only. It is not part of the
M.A.X.I.N.E. production proof chain, O3DE runtime, Asset Processor Batch
diagnostics, Editor bridge behavior, prefab mutation routes, release packaging,
or animation validation.

## What It Is

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) is a
developer plugin that analyzes a repository and writes an interactive knowledge
graph. Its upstream README describes it as a way to turn codebases, knowledge
bases, and docs into a graph that can be searched, explored, and queried.

As of the upstream inspection on 2026-05-14:

- Repository: `Lum1104/Understand-Anything`
- License: MIT
- Default branch: `main`
- Codex support: provided through the install scripts and skills installed into
  the user's agent skills directory
- Basic use: run `/understand`, then explore with `/understand-dashboard`,
  `/understand-chat`, and `/understand-diff`

## Why Consider It Here

This repository has several tightly related production-readiness surfaces:

- O3DE integration scripts under `tools/o3de/`
- `MaxineRuntimeExitFixture` Gem bridge and runtime fixture code
- Editor smoke diagnostics and prefab mutation routes
- Asset Processor Batch diagnostics and product-matrix validation
- Runtime harness diagnostics and no-defaultlevel fixture evidence
- Manifests, QC validation, sanitized evidence, status docs, and PR handoffs

Understand-Anything can help a developer build a mental map of those
relationships faster. It can answer onboarding questions like "which files
coordinate Editor smoke diagnostics?" or "what docs describe runtime harness
proof limits?" from a generated graph.

## What It Must Not Prove

Understand-Anything output is not O3DE evidence. Do not use its graph, chat
answers, dashboard, or diff overlay as proof for:

- APB product generation or spawnable regeneration
- Runtime Actor, Simple Motion, or Anim Graph component presence
- Runtime asset assignment verification
- Animation playback
- Full runtime character behavior
- Editor bridge, prefab mutation, or source-template persistence
- Publication, release packaging, or production-ready status

It is a developer comprehension aid only.

## Safe Installation For Codex

Do not pipe remote install scripts directly into a shell for this repository.
Inspect the installer first, then run it intentionally from a local checkout if
you choose to install it.

Recommended safe flow on Windows:

```powershell
gh repo clone Lum1104/Understand-Anything "$env:TEMP\Understand-Anything-review"
Get-Content "$env:TEMP\Understand-Anything-review\install.ps1"
Set-Location "$env:TEMP\Understand-Anything-review"
.\install.ps1 codex
```

The upstream PowerShell installer:

- clones or updates the plugin checkout at `$HOME\.understand-anything\repo`
  unless `UA_DIR` overrides it
- creates per-skill junctions for Codex under `$HOME\.agents\skills`
- creates a universal plugin-root junction at
  `$HOME\.understand-anything-plugin`
- keeps the cloned checkout when uninstalling skill links

The upstream Bash installer follows the same model on macOS/Linux, using
`$HOME/.understand-anything/repo`, `$HOME/.agents/skills`, and
`$HOME/.understand-anything-plugin`.

No repository-specific secrets were identified in the upstream README or
installer. Installation does require network access to GitHub and package
installation may require Node.js and `pnpm`. The dashboard uses a local Vite
server URL with an access token in the query string; treat that URL as local
session data, not as a repository artifact.

## Running The Workflow

From the repository root, run:

```text
/understand --no-auto-update
```

Use `--no-auto-update` for this repository unless the team intentionally wants
the plugin to write auto-update configuration or hooks. For a full rebuild:

```text
/understand --full --no-auto-update
```

If the graph is too large or the scan asks for confirmation because the repo has
many files, scope the run to a smaller area first, such as:

```text
/understand tools/o3de --no-auto-update
/understand o3de/gems/MaxineRuntimeExitFixture --no-auto-update
```

## Exploring The Graph

Open the dashboard:

```text
/understand-dashboard
```

The dashboard reads `.understand-anything/knowledge-graph.json` and starts a
local Vite server. Use the full local URL printed by the command, including its
token parameter.

Ask focused questions:

```text
/understand-chat How do runtime harness diagnostics connect to APB evidence?
/understand-chat Which files participate in approved source prefab updates?
/understand-chat What should I read before changing MaxineRuntimeExitFixture?
```

Analyze branch impact:

```text
/understand-diff
```

`/understand-diff` writes `.understand-anything/diff-overlay.json`, which is
local scratch data and must not be committed.

Regenerate after major changes:

```text
/understand --full --no-auto-update
```

Regenerate after a narrow docs or code change:

```text
/understand --no-auto-update
```

## Repo-Local Files

Upstream behavior writes these files under `.understand-anything/`:

- `knowledge-graph.json`: main graph used by dashboard and chat
- `meta.json`: analyzed commit and timestamp metadata
- `fingerprints.json`: structural fingerprints for incremental updates
- `config.json`: local plugin preferences, such as auto-update or language
- `.understandignore`: scan-exclusion hints
- `intermediate/`: temporary analysis output
- `tmp/`: temporary validation scripts
- `diff-overlay.json`: local diff visualization data

This repository ignores local scratch outputs:

```gitignore
.understand-anything/intermediate/
.understand-anything/tmp/
.understand-anything/diff-overlay.json
.understand-anything/dashboard/
.understand-anything/cache/
.understand-anything/logs/
```

Commit `knowledge-graph.json`, `meta.json`, `fingerprints.json`, `config.json`,
or `.understandignore` only after review. If `knowledge-graph.json` is larger
than roughly 10 MB, prefer regeneration or Git LFS rather than normal Git
tracking. Do not commit `node_modules`, temporary plugin checkouts, generated
dashboards, caches, logs, local access-token URLs, secrets, or machine-specific
symlinks/junctions.

## Uninstalling

From a reviewed local checkout of `Lum1104/Understand-Anything`:

```powershell
.\install.ps1 -Uninstall codex
```

The uninstall path removes skill links and the universal plugin-root junction,
but keeps `$HOME\.understand-anything\repo` in case other tools still use it.
Remove that checkout manually only after confirming no other platform depends on
it.

## Production Isolation Rules

Keep Understand-Anything out of:

- `tools/o3de/runtime_harness.py`
- `tools/o3de/asset_processor_batch.py`
- `tools/o3de/editor_smoke.py`
- `o3de/gems/MaxineRuntimeExitFixture/`
- APB, runtime, Editor bridge, prefab mutation, and production readiness gates

Never use it to replace source validation against local O3DE or repo-owned
bridge/runtime code. It can help decide what to read next; it cannot certify
what O3DE did.
