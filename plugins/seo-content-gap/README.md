# seo-content-gap (plugin)

The plugin package. Installed via the marketplace at the repo root.

- **Commands:** `/seo-gap`, `/seo-gap-help`
- **Agents:** `page-extractor` (URL → structured block JSON), `competitor-finder` (SERP
  discovery + ranking check), `gap-analyst` (alignment + clustering + gap engine)
- **Skill:** `seo-content-gap` (`skills/seo-content-gap/SKILL.md`) — the orchestrator and the
  conversational session.
- **Reference:** extraction schema, gap rubric, brief template, content-quality checklist
  (`skills/seo-content-gap/reference/`).
- **Script:** `scripts/build_report.py` — turns the run's JSON into `report.html` (charts +
  filterable gap table) and `report.xlsx` (KPI filters); CSV fallback if `openpyxl` is absent.

See the repo-root `README.md` and `docs/USAGE.md`.
