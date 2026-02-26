Review the complete system (Steps 9-17) and decide whether to approve deployment.

## Instructions

1. Read the SOT (`.claude/state.yaml`) to confirm current_step is 18
2. Review Implementation Phase outputs:
   - Step 9: Project infrastructure scaffolding
   - Steps 10-11: Crawling core + 44 site adapters
   - Step 12: Crawling pipeline integration
   - Steps 13-14: Analysis pipeline Stages 1-8
   - Step 15: Analysis pipeline integration
   - Step 16: E2E test report (`testing/e2e-test-report.md`)
   - Step 17: Automation and scheduling
3. Validate completeness:
   - Run: `python3 scripts/validate_code_structure.py --step 9 --project-dir .`
   - Run: `python3 scripts/validate_code_structure.py --step 11 --check-adapters --project-dir .`
   - Run: `python3 scripts/validate_code_structure.py --step 15 --project-dir .`
   - Read E2E test results — verify PRD §9.1 metrics:
     - Success rate ≥ 80% (≥ 35/44 sites)
     - Total articles ≥ 500
     - Dedup effectiveness ≥ 90%
     - Per-site time ≤ 5 minutes
     - Memory peak ≤ 10GB
4. Present summary to user with:
   - Test results dashboard
   - Any failing sites and reasons
   - Code quality assessment
   - Recommendation: DEPLOY or REWORK specific components
5. Options:
   - **deploy**: Advance to Step 19 (Documentation)
   - **rework [step]**: Re-execute specified Implementation step
   - **retest**: Re-run E2E tests after fixes
