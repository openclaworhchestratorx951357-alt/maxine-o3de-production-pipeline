# MAX_BIPED_v1

`MAX_BIPED_v1` is the canonical biped skeleton contract for release-lane MAXINE characters.

## Coordinate Contract

- 1 meter equals 1 O3DE world unit.
- Release exports are Z-up.
- Release exports are origin-centered.
- Forward direction must be declared.
- The `root` bone must be at scene origin.
- `pelvis` must be a child of `root`.

## Required Bones

Required bones are:

`root`, `pelvis`, `spine_01`, `spine_02`, `neck`, `head`, `clavicle_l`, `upperarm_l`, `lowerarm_l`, `hand_l`, `clavicle_r`, `upperarm_r`, `lowerarm_r`, `hand_r`, `thigh_l`, `calf_l`, `foot_l`, `ball_l`, `thigh_r`, `calf_r`, `foot_r`, `ball_r`.

Release retargeting expects identical hierarchy and names unless a future waiver is explicitly recorded. Hero characters require facial morph inventory. NPCs may use an approved facial waiver, which remains a warning.

Dynamic characters must use primitive or convex collision policy for release. The current validator is metadata/fixture-based and does not parse FBX; FBX inspection is a future integration extension.
