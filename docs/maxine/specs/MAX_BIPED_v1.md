# MAX_BIPED_v1 Skeleton Spec

## Purpose

`MAX_BIPED_v1` defines a manifest-attachable skeleton contract for release-lane character evidence in M.A.X.I.N.E. It standardizes required core bones, hierarchy relationships, naming expectations, and severity outcomes so skeleton conformance can be reported deterministically.

## Release-Lane Scope

- Primary scope: `release_character` lane readiness evidence.
- This slice does not execute O3DE, Asset Processor, spawn, publish, or cache/database access.
- This slice defines contract + validation evidence only.

## Character Tier Usage

- `npc`: fully supported target tier.
- `hero`: fully supported target tier.
- `draft`: allowed for early checks; warnings are expected more often.
- `test`: allowed for CI and fixture validation.

## Coordinate Assumptions

- Expected up axis: `Z`.
- Expected forward axis: `Y`.
- Expected handedness: `right`.
- Unknown/mismatched coordinate metadata is a validation finding and may require manual review depending on severity mapping.

## Unit Assumptions

- Expected linear unit: `meters`.
- Unknown/mismatched units are reported as findings and can drive `warn` or `pending_manual`.

## Root Bone Requirements

- Required root bone name: `root`.
- `root` must exist exactly once in the skeleton inventory.
- Missing root is a `fail`.

## Pelvis/Hip Relationship

- Accepted pelvis bone names: `pelvis`, `hip`.
- At least one accepted pelvis name must exist.
- If multiple accepted pelvis candidates exist, result is `pending_manual`.
- The selected pelvis/hip bone must be a direct child of `root`.
- Missing pelvis/hip or invalid parent relationship is a `fail`.

## Required Core Bone Names

- `root`
- `pelvis`
- `spine_01`
- `spine_02`
- `neck`
- `head`
- `clavicle_l`, `clavicle_r`
- `upperarm_l`, `upperarm_r`
- `lowerarm_l`, `lowerarm_r`
- `hand_l`, `hand_r`
- `thigh_l`, `thigh_r`
- `calf_l`, `calf_r`
- `foot_l`, `foot_r`

## Optional Twist/Helper Bones

- Optional examples:
  - `upperarm_twist_01_l`, `upperarm_twist_01_r`
  - `lowerarm_twist_01_l`, `lowerarm_twist_01_r`
  - `thigh_twist_01_l`, `thigh_twist_01_r`
  - `calf_twist_01_l`, `calf_twist_01_r`
- Missing one side for optional twist/helper pairs typically produces `warn`.

## Optional Facial Bones / Blend-Shape Relationship

- Facial bones are optional in this slice.
- Blend-shape data is out of scope for this validator, but contract findings should be attachable to manifest QC for later facial/shape checks.

## Naming Rules

- Bone names use lowercase snake-like format with side suffixes when sided.
- Side suffix convention:
  - left: `_l`
  - right: `_r`
- Required sided bone bases must follow paired naming (for example `upperarm_l` and `upperarm_r`).

## Hierarchy Rules

- Required parent-child edges include:
  - `root -> pelvis`
  - `pelvis -> spine_01`
  - `spine_01 -> spine_02`
  - `spine_02 -> neck`
  - `neck -> head`
  - `clavicle_l -> upperarm_l`
  - `upperarm_l -> lowerarm_l`
  - `lowerarm_l -> hand_l`
  - `clavicle_r -> upperarm_r`
  - `upperarm_r -> lowerarm_r`
  - `lowerarm_r -> hand_r`
  - `pelvis -> thigh_l`
  - `thigh_l -> calf_l`
  - `calf_l -> foot_l`
  - `pelvis -> thigh_r`
  - `thigh_r -> calf_r`
  - `calf_r -> foot_r`

## Left/Right Naming Convention

- Required mirrored core limbs must have both `_l` and `_r`.
- Missing mirror on required core limbs is a `fail`.
- Missing mirror on optional twist/helper limbs is a `warn`.

## Forbidden Patterns

- Whitespace in bone names.
- Uppercase letters in bone names.
- Path-like separators (`/`, `\`) in bone names.
- Parent traversal tokens (`..`) in bone names.

## Validation Severity Levels

- `pass`: no warnings/failures/manual-review findings.
- `warn`: only warning-level findings present.
- `fail`: one or more fail-level findings.
- `pending_manual`: no fail findings, but at least one manual-review finding.

## Status Triggers

- `pass`: required bones and hierarchy edges are valid, naming rules pass, no warning/manual-only findings.
- `warn`: optional mirror/helper issues or non-blocking metadata mismatches only.
- `fail`: missing root/core bones, invalid required hierarchy, forbidden naming pattern hits, pelvis/root hard-rule breaks.
- `pending_manual`: ambiguous pelvis candidate resolution or contract-configured manual-review situations.

## Manifest Attachment

- Validator output emits a normalized QC check object for manifest attachment.
- Current manifest target path: `qc.gates[]`.
- Future-compatible path: `qc.checks[]`.
- Suggested check id: `max_biped_v1_skeleton_contract`.
