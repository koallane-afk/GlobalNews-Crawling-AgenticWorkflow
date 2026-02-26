Review the Planning Phase (Steps 5-7) outputs and decide whether to proceed to the Implementation Phase.

## Instructions

1. Read the SOT (`.claude/state.yaml`) to confirm current_step is 8
2. Read all Planning Phase outputs:
   - Step 5: `planning/architecture-blueprint.md` — System architecture
   - Step 6: `planning/crawling-strategies.md` — Per-site crawling strategies (44 sites)
   - Step 7: `planning/analysis-pipeline-design.md` — 8-stage analysis pipeline
3. Validate completeness:
   - Run: `python3 scripts/validate_data_schema.py --step 5 --project-dir .`
   - Run: `python3 scripts/validate_site_coverage.py --file planning/crawling-strategies.md --project-dir .`
   - Run: `python3 scripts/validate_technique_coverage.py --file planning/analysis-pipeline-design.md --project-dir .`
   - Verify Parquet schemas match PRD §7.1
   - Verify all 44 sites have detailed crawling strategies
   - Verify all 56 analysis techniques are mapped to stages
   - Verify memory estimates fit M2 Pro 16GB
4. Present summary to user with:
   - Architecture overview
   - Coverage verification results
   - Any design concerns
   - Recommendation: PROCEED to Implementation or REWORK specific steps
5. Options:
   - **proceed**: Advance to Step 9 (Project Infrastructure)
   - **rework [step]**: Re-execute specified Planning step
   - **modify**: Adjust architecture or strategies before proceeding
