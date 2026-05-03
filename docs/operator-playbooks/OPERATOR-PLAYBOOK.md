# Operator Playbook

This playbook is for operators who run the pipeline without needing to edit code.

## 1) Submit a Photo Mesh Job

1. Place the source photo in the approved intake location.
2. Create a job payload selecting `photo_mesh` lane.
3. Set character name and tier as draft.
4. Submit the job through the intake command or queue drop.
5. Wait for job status to move from `queued` -> `running` -> final state.

## 2) Submit a Text Mesh Job

1. Create a job payload selecting `text_mesh`.
2. Enter the character prompt text and character name.
3. Submit to queue.
4. Confirm final manifest is created and status recorded.

## 3) Submit Rig-Prep Job

1. Choose `photo_rig_prep` or `text_full_rig` lane.
2. Submit with required source and identity fields.
3. Confirm the job reaches either `pass` or `pending_manual`.
4. If pending, follow manual rig handoff notes in manifest.

## 4) Resume Pending Manual Rig Job

1. Open the pending job manifest.
2. Fill in rigged FBX input reference from manual handoff.
3. Submit resume job as `external_rig_import`.
4. Verify resumed job links back to original job ID chain.

## 5) Import Rigged FBX

1. Provide rigged FBX path and character identity.
2. Provide optional motion clips if available.
3. Run import lane.
4. Confirm `.actor` and motion products resolve in output manifest.

## 6) Review Manifest and Evidence

1. Open manifest JSON.
2. Check `job.status`, `job.lane`, and `qc.overall`.
3. Inspect evidence links (logs/screenshots/reports).
4. Confirm provenance and cleanup sections are present.

## 7) Retry Failed Jobs

1. Duplicate failed job payload or use retry utility.
2. Keep original job reference in provenance.
3. Re-submit with corrected inputs.
4. Verify new manifest emits a new job ID and references previous failure.

## 8) Publish Release Package

1. Ensure all required QC gates pass or approved warning policy exists.
2. Confirm final manifest includes runtime validation and evidence.
3. Run publish command for prefab/actor package.
4. Record publication metadata and rollback path.
5. Mark operation complete only after evidence bundle is attached.

## Operator Rules

- Never place secrets in job files.
- Never treat a spawn-only result as release-complete.
- Every job, including failures, must have a manifest record.
- Escalate `warn` and `pending_manual` outcomes for review before release promotion.
