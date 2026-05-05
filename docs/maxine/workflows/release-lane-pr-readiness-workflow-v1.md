# Release-Lane PR Readiness Workflow v1

## Purpose

This workflow prevents feature drift once a release-lane branch reaches proof-ready state. After the trigger conditions are met, Codex must stop adding feature work on that branch and focus only on PR-readiness and handoff.

## When PR-readiness mode applies

PR-readiness mode applies when all of the following are true:

- a branch-level readiness report exists
- pilot chain runner passes
- proof flow passes
- safety verifier passes
- PowerShell safety wrapper passes
- targeted/full tests pass as required
- branch has meaningful diff against main
- no uncommitted source/doc/test changes remain

## Required behavior in PR-readiness mode

When PR-readiness mode applies, Codex must:

- stop feature work
- do not create more standalone validators
- do not add new release gates
- do not widen execution surfaces
- execution remains future work requiring explicit approval
- run required validation commands before opening/updating PR
- prepare/open PR
- report merge recommendation
- start future capability/execution-admission work only from updated `main` after merge

## Required validation commands

Run these commands exactly:

```powershell
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git status --short --untracked-files=all
git branch --show-current
git log --oneline -5
git branch -vv
git branch -r

git rev-list --left-right --count main...origin/<branch-name>
git log --oneline main..origin/<branch-name> -20
git checkout <branch-name>
git status --short --untracked-files=all
git rev-parse HEAD
git rev-list --left-right --count main...HEAD

python tools/release-lane/run_pilot_release_chain_validation.py
python tools/release-lane/prove_pilot_release_chain.py
python -m pytest tests/pytest/test_pilot_release_chain_ci_proof.py tests/pytest/test_release_lane_evidence_admission_status.py -q
git diff --check
python tools/audit/verify_sandbox_writer_safety.py
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\Test-MaxineSandboxWriterSafety.ps1
python -m pytest tests/pytest -q
powershell -NoProfile -Command "Invoke-Pester -Path .\tests\pester"
```

## Runtime artifact cleanup

Generated proof artifacts may appear under:

- `examples/sandbox/manifests/reports/pilot-release-chain-proof/`

These outputs are runtime proof artifacts unless intentionally tracked. Codex must not commit runtime-only generated artifacts accidentally.

## PR creation fallback

If PR creation is unavailable, Codex must output:

- create-PR URL
- PR title
- PR body
- validation summary
- merge recommendation

## Standard PR title

Use:

- `Finalize evidence-only pilot release-lane chain v1`

## Standard PR body template

```markdown
## Summary
Finalizes the evidence-only pilot release-lane chain for review. The branch includes the branch-level readiness report and README current-state pointer and does not add any new execution capability.

## Pilot chain status
- `run_pilot_release_chain_validation.py`: pass
- `prove_pilot_release_chain.py`: pass
- `pilot_chain_status=pass`
- `final_gate_count=23`
- strict proof run passes

## Evidence/admission posture
- Evidence-only pilot release chain is operational
- AAA-quality output is not fully operational yet
- Execution admission remains future work requiring explicit approval
- No publication/O3DE/AP/Blender/spawn/cache/live-DB execution is admitted

## Files highlighted
- `README.md`
- `docs/maxine/release-lane-pilot-readiness-report-v1.md`

## Validation results
- targeted pytest: pass
- full pytest: pass
- full Pester: pass
- pilot runner/proof: pass
- safety verifier: pass
- PowerShell safety wrapper: pass
- `git diff --check`: pass

## Safety boundary statement
No boundary widening is introduced. Existing blocked/unadmitted surfaces remain blocked:
- no broad O3DE execution
- no broad/real Asset Processor execution for publication flow
- no Blender/DCC execution
- no spawn/publish execution
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production path or engine path writes

## AAA-quality alignment
This branch establishes an operational evidence-only pilot release chain. It does not make AAA-quality output fully operational. Controlled real evidence coverage, explicit execution-admission approval, and admitted execution receipts remain future work.

## Remaining risks
- controlled real evidence remains limited
- explicit approved execution-admission decision is absent
- admitted real execution receipt chain is absent

## Next recommended task
Merge this branch first, then start explicit execution-admission review/decision work from `main` on a new branch.
```
