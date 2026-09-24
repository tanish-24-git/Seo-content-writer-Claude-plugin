# seo-content-gap (plugin)

The plugin package. Installed via the marketplace at the repo root.

- **Commands:** `/seo-gap`, `/seo-gap-help`
- **Agents:** `page-extractor` (URL → structured block JSON), `competitor-finder` (SERP
  discovery + ranking check), `gap-analyst` (alignment + clustering + gap engine)
- **Skill:** `seo-content-gap` (`skills/seo-content-gap/SKILL.md`) — the orchestrator and the
  conversational session.
- **Reference:** extraction schema, gap rubric, brief template, content-quality checklist
  (`skills/seo-content-gap/reference/`).
- **Scripts:**
  - `scripts/build_report.py` — turns the run's JSON into `report.html`, `report.pdf` (via local
    Chrome/Edge) and `report.xlsx` (CSV fallback if `openpyxl` is absent). Renderers live in
    `report_core.py`, `report_html.py`, `report_xlsx.py`, `report_pdf.py`.
  - `scripts/fetch_pagespeed.py` — Core Web Vitals + Lighthouse for every page → `pagespeed.json`.
  - `scripts/fetch_ahrefs.py` — URL/Domain Rating, backlinks, organic keywords → `authority.json`
    (REST with `AHREFS_API_KEY`, or assembled from Ahrefs connector responses).

See the repo-root `README.md` and `docs/USAGE.md`.
