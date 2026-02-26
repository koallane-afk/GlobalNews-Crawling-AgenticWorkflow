Review the Research Phase (Steps 1-3) outputs and decide whether to proceed to the Planning Phase.

## Instructions

1. Read the SOT (`.claude/state.yaml`) to confirm current_step is 4
2. Read all Research Phase outputs:
   - Step 1: `research/site-reconnaissance.md` — 44 news site analysis
   - Step 2: `research/tech-validation.md` — Technology stack validation
   - Step 3: `research/crawling-feasibility.md` — Crawling feasibility analysis
3. Validate completeness:
   - Run: `python3 scripts/validate_site_coverage.py --file research/site-reconnaissance.md --project-dir .`
   - Verify all 44 sites have reconnaissance data
   - Verify tech stack is viable on M2 Pro 16GB
   - Verify all sites have primary + fallback crawling strategies
4. Present summary to user with:
   - Key findings from each step
   - Any risks or concerns identified
   - Recommendation: PROCEED to Planning or REWORK specific steps
5. Options:
   - **proceed**: Advance to Step 5 (System Architecture)
   - **rework [step]**: Re-execute specified Research step
   - **modify**: Adjust site list or requirements before proceeding
