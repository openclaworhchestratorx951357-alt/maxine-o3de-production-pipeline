# Natural Language O3DE Control Pack v1

## Purpose
This pack is the first production-control layer for asking M.A.X.I.N.E. to control O3DE in natural language without losing the repository's existing safety, validation, and evidence logic.

The core idea is simple:

```text
natural language request -> guarded command envelope -> validator -> admitted tool/action -> receipt/evidence
```

## What Exists In This Slice
- A command schema: `schemas/maxine_nl_o3de_control_command.schema.json`
- A natural-language compiler: `tools/nl-o3de-control/compile_nl_o3de_command.py`
- A command validator: `tools/nl-o3de-control/validate_nl_o3de_control_command.py`
- Passing and blocked examples under `examples/nl-o3de-control/`
- Pytest coverage under `tests/pytest/test_nl_o3de_control_command.py`

## Production Meaning
This is not a chatbot prompt file. It is a control boundary.

The agent may accept a normal sentence, but it must convert that sentence into a structured command before it can touch O3DE-related workflows. The command records:
- what the user asked for
- what intent the agent inferred
- what execution mode is requested
- what actions are allowed
- what actions remain forbidden
- which evidence/admission artifacts are being used
- whether approval is required
- where outputs are allowed to go

## Current Admitted Modes
The v1 validator allows these modes to pass:
- `read_only`
- `evidence_only`
- `noop_receipt`
- `dry_run_planning`

These are intentionally bounded. They let the agent inspect, validate, plan, and produce controlled evidence.

## Blocked Until Later Admission
The command schema can represent these future modes, but v1 does not admit them automatically:
- `sandbox_dry_run`
- `real_execution`
- `publication`

Those modes require explicit admission records, approval phrases, receipts, rollback evidence, and O3DE adapter implementation before they should pass.

## Example Commands
```powershell
python tools/nl-o3de-control/compile_nl_o3de_command.py "Inspect the latest MAXINE actor products in O3DE"
```

```powershell
python tools/nl-o3de-control/validate_nl_o3de_control_command.py examples/nl-o3de-control/nl_o3de_control_command_inspect_actor_products_v1.json
```

```powershell
python tools/nl-o3de-control/validate_nl_o3de_control_command.py examples/nl-o3de-control/nl_o3de_control_command_prepare_publication_dry_run_blocked_v1.json
```

## How This Becomes Complete O3DE Control
The next production layers should be added in this order:

1. Natural language command envelope v1
2. Read-only O3DE project and Asset Processor inspection adapter
3. Manifest and release-lane command router
4. Sandbox dry-run adapter with receipts
5. O3DE editor automation adapter behind explicit approval
6. Prefab/actor publication adapter behind explicit approval
7. Operator dashboard or CLI for reviewing requests, approvals, receipts, and rollback evidence

The important bit: every layer keeps the same pattern. Natural language never directly mutates O3DE. It becomes a validated command first.

## Operator Promise
The user should be able to say:

```text
Inspect my latest MAXINE actor products and prepare a publication dry run.
```

The system should respond by generating a command envelope, validating it, running only admitted checks, writing evidence in sandbox paths, and clearly reporting what remains blocked.

