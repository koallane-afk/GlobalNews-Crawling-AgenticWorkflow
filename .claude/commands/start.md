Start the workflow from the current step. This command is the single entry point for workflow execution.

## Instructions

1. Run the startup script to get structured context:
   ```
   python3 scripts/workflow_starter.py --project-dir .
   ```

2. Parse the JSON output and check `readiness`:
   - **`blocked`**: Report blocking reasons to user. Do NOT proceed.
   - **`completed`**: Inform user the workflow is already complete.
   - **`ready`**: Proceed to step 3.

3. Display startup summary to user:
   ```
   ── WORKFLOW START ──────────────────────────
   Step {current_step}/{total_steps} — {phase} Phase
   {step_name}
   Agent: {agent/team}
   Output: {output_path}
   Autopilot: {on/off}
   ─────────────────────────────────────────────
   ```

4. Read the current step's detailed guide from the playbook:
   ```
   python3 scripts/extract_orchestrator_step_guide.py --step {current_step} --project-dir . --include-universal --include-failure-recovery
   ```

5. Read the current step's Verification criteria from `prompt/workflow.md` (Step {current_step} section).

6. Begin executing the Universal Step Protocol:
   - Follow the `next_actions` checklist from the starter output
   - For each action, execute in order (no skipping)
   - Record all outputs via `sot_manager.py --record-output`
   - Run quality gates via `scripts/run_quality_gates.py`
   - Validate transition via `scripts/validate_step_transition.py`
   - Advance via `sot_manager.py --advance-step`

7. After step completion:
   - If autopilot is ON: automatically proceed to the next step (loop back to step 1 of this command)
   - If autopilot is OFF: report completion and wait for user instruction

## Autopilot Variant

If the user says "autopilot으로 시작" or similar:
```
python3 scripts/workflow_starter.py --project-dir . --autopilot
```
Then also update SOT:
```
python3 scripts/sot_manager.py --set-autopilot true --project-dir .
```

## Error Handling

- If any quality gate fails: follow the Abductive Diagnosis protocol (CLAUDE.md §Autopilot)
- If a script is missing: report to user and suggest running `/install`
- If SOT is corrupted: suggest `python3 scripts/sot_manager.py --init --workflow-name "GlobalNews Auto-Build" --total-steps 20 --project-dir .`
