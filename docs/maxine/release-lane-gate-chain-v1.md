# Release-Lane Gate Chain v1

This consolidation checkpoint indexes the release-lane gates in sequence and marks current implementation state.

- This document does **not** make AAA output fully operational.
- Current gates are mostly evidence/report validators.
- `source_product_evidence_resolver_v1` is the correction back toward deterministic source/product evidence.
- Publication, spawn, O3DE execution, and broad AP execution remain blocked unless a future admission slice explicitly changes that.

## Chain Index

| order | check_id | purpose | schema path | validator path | golden example path | manifest attachment | required tier | current evidence source | execution admitted | required before publication-ready | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `max_biped_v1_skeleton_contract` | skeleton contract compliance | `schemas/maxine_skeleton_contract.schema.json` | `tools/skeleton-validator/validate_skeleton_contract.py` | `examples/skeletons/max_biped_v1_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture | no | yes | implemented |
| 2 | `dcc_conform_v1` | DCC conform evidence quality | `schemas/maxine_dcc_conform_report.schema.json` | `tools/dcc-conform/validate_dcc_conform_report.py` | `examples/sandbox/dcc-conform-evidence/pilot-candidates/max_biped_v1_dcc_conform_controlled_real.fixture.json` | `qc.gates[]` now, `qc.checks[]` later | all | controlled real fixture/import evidence | no | yes | implemented |
| 3 | `source_product_evidence_resolver_v1` | deterministic source->product evidence bridge without live ID claims | `schemas/maxine_source_product_evidence_resolver_report.schema.json` | `tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py` | `examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/imported AP evidence | no | yes | implemented |
| 4 | `material_uv_qc_v1` | material/UV evidence quality | `schemas/maxine_material_uv_qc_report.schema.json` | `tools/material-uv-qc/validate_material_uv_qc_report.py` | `examples/material-uv-qc/max_biped_v1_material_uv_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 5 | `animation_smoke_v1` | animation smoke evidence quality | `schemas/maxine_animation_smoke_report.schema.json` | `tools/animation-smoke/validate_animation_smoke_report.py` | `examples/animation-smoke/max_biped_v1_animation_smoke_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 6 | `screenshot_evidence_v1` | visual evidence completeness | source-index contract (`examples/screenshot-evidence/max_biped_v1_screenshot_source_index.json`) | `tools/screenshot-evidence/extract_screenshot_evidence_index.py` | `examples/sandbox/evidence-sources/screenshots/pilot-shot-001.txt` | `qc.gates[]` now, `qc.checks[]` later | all | controlled fixture extractor | no | yes | implemented (fixture extractor) |
| 7 | `manual_hero_review_v1` | human decision gate for hero assets | `schemas/maxine_manual_hero_review_report.schema.json` | `tools/manual-hero-review/validate_manual_hero_review_report.py` | `examples/manual-hero-review/max_biped_v1_manual_hero_review_pass.json` | `qc.gates[]` now, `qc.checks[]` later | hero | manual report | no | yes | implemented |
| 8 | `ci_artifact_retention_v1` | CI evidence retention policy | `schemas/maxine_ci_artifact_retention_report.schema.json` | `tools/ci-artifact-retention/validate_ci_artifact_retention_report.py` | `examples/ci-artifact-retention/max_biped_v1_ci_artifact_retention_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 9 | `release_package_bundle_v1` | release package bundle integrity | `schemas/maxine_release_package_bundle_report.schema.json` | `tools/release-package-bundle/validate_release_package_bundle_report.py` | `examples/release-package-bundle/max_biped_v1_release_package_bundle_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 10 | `release_promotion_decision_v1` | promotion decision policy gate | `schemas/maxine_release_promotion_decision_report.schema.json` | `tools/release-promotion-decision/validate_release_promotion_decision_report.py` | `examples/release-promotion-decision/max_biped_v1_release_promotion_decision_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 11 | `release_publication_preflight_v1` | pre-publication readiness check | `schemas/maxine_release_publication_preflight_report.schema.json` | `tools/release-publication-preflight/validate_release_publication_preflight_report.py` | `examples/release-publication-preflight/max_biped_v1_release_publication_preflight_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 12 | `release_publication_request_approval_v1` | publication request approval evidence | `schemas/maxine_release_publication_request_approval_report.schema.json` | `tools/release-publication-request-approval/validate_release_publication_request_approval_report.py` | `examples/release-publication-request-approval/max_biped_v1_release_publication_request_approval_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 13 | `release_publication_execution_admission_gate_v1` | execution admission policy gate | `schemas/maxine_release_publication_execution_admission_gate_report.schema.json` | `tools/release-publication-execution-admission-gate/validate_release_publication_execution_admission_gate_report.py` | `examples/release-publication-execution-admission-gate/max_biped_v1_release_publication_execution_admission_gate_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 14 | `release_publication_execution_request_ledger_v1` | execution request ledger integrity | `schemas/maxine_release_publication_execution_request_ledger_report.schema.json` | `tools/release-publication-execution-request-ledger/validate_release_publication_execution_request_ledger_report.py` | `examples/release-publication-execution-request-ledger/max_biped_v1_release_publication_execution_request_ledger_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 15 | `release_publication_execution_receipt_v1` | execution receipt evidence | `schemas/maxine_release_publication_execution_receipt_report.schema.json` | `tools/release-publication-execution-receipt/validate_release_publication_execution_receipt_report.py` | `examples/release-publication-execution-receipt/max_biped_v1_release_publication_execution_receipt_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 16 | `release_publication_rollback_drill_v1` | rollback drill readiness evidence (non-executing) | fixture attachment payload (no standalone schema yet) | attached via `tools/release-lane/run_pilot_release_chain_validation.py` | `examples/manifest-qc-attachments/max_biped_v1_release_publication_rollback_drill_attach_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture attachment | no | yes | implemented (fixture) |
| 17 | `release_publication_evidence_integrity_index_v1` | evidence integrity indexing | `schemas/maxine_release_publication_evidence_integrity_index_report.schema.json` | `tools/release-publication-evidence-integrity-index/validate_release_publication_evidence_integrity_index_report.py` | `examples/release-publication-evidence-integrity-index/max_biped_v1_release_publication_evidence_integrity_index_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 18 | `release_publication_chain_audit_bundle_v1` | chain audit bundle integrity | `schemas/maxine_release_publication_chain_audit_bundle_report.schema.json` | `tools/release-publication-chain-audit-bundle/validate_release_publication_chain_audit_bundle_report.py` | `examples/release-publication-chain-audit-bundle/max_biped_v1_release_publication_chain_audit_bundle_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 19 | `release_publication_ready_for_execution_request_v1` | ready-for-execution request readiness evidence (non-executing) | fixture attachment payload (no standalone schema yet) | attached via `tools/release-lane/run_pilot_release_chain_validation.py` | `examples/manifest-qc-attachments/max_biped_v1_release_publication_ready_for_execution_request_attach_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture attachment | no | yes | implemented (fixture) |
| 20 | `release_publication_execution_handoff_v1` | execution handoff completeness | `schemas/maxine_release_publication_execution_handoff_report.schema.json` | `tools/release-publication-execution-handoff/validate_release_publication_execution_handoff_report.py` | `examples/release-publication-execution-handoff/max_biped_v1_release_publication_execution_handoff_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 21 | `release_publication_execution_admission_request_packet_v1` | admission request packet completeness | `schemas/maxine_release_publication_execution_admission_request_packet_report.schema.json` | `tools/release-publication-execution-admission-request-packet/validate_release_publication_execution_admission_request_packet_report.py` | `examples/release-publication-execution-admission-request-packet/max_biped_v1_release_publication_execution_admission_request_packet_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |
| 22 | `release_publication_gate_set_v1` | complete gate sequence/order validator | `schemas/maxine_release_publication_gate_set_report.schema.json` | `tools/release-publication-gate-set/validate_release_publication_gate_set_report.py` | `examples/release-publication-gate-set/max_biped_v1_release_publication_gate_set_pass.json` | `qc.gates[]` now, `qc.checks[]` later | all | fixture/manual report | no | yes | implemented |

## Operational Note

AAA-quality output is still not fully operational. Before that state, the project still needs:

- pilot chain fixture + validator are now available:
  - `examples/manifests/example-release-character-pilot-chain.manifest.json`
  - `tools/release-lane/validate_pilot_release_chain.py`
- deterministic pilot attachment runner is now available:
  - `tools/release-lane/run_pilot_release_chain_validation.py`
  - `examples/manifests/example-release-character-pilot-chain-base.manifest.json`
- evidence/admission status reporter is now available:
  - `tools/release-lane/report_release_lane_evidence_admission_status.py`
  - `docs/maxine/specs/release-lane-evidence-admission-status-v1.md`
- bounded source/product evidence extraction is now available:
  - `tools/release-lane/extract_source_product_evidence_resolver_report.py`
  - `docs/maxine/specs/source-product-evidence-real-extraction-v1.md`
- bounded controlled-real DCC conform evidence is now available:
  - `docs/maxine/specs/controlled-real-dcc-conform-evidence-v1.md`
  - `examples/sandbox/dcc-conform-evidence/pilot-candidates/max_biped_v1_dcc_conform_controlled_real.fixture.json`
- bounded real evidence extraction from controlled sources
- controlled O3DE/AP evidence integration (still blocked today)
- promotion from fixture proof to controlled real evidence across the chain
- human review and rollback validation
