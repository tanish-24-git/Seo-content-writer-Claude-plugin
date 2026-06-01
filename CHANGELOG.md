# Changelog

All notable changes to the SEO Content-Gap plugin are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-02
### Added
- Initial release.
- `/seo-gap` command — guided, single-page competitor content-gap analysis.
- `/seo-gap-help` command.
- Sub-agents: `page-extractor`, `competitor-finder`, `gap-analyst`.
- `seo-content-gap` skill — the 6-stage orchestration + conversational session.
- SERP ranking check (reports whether your page and competitors rank for the topic).
- Block-to-block + FAQ-to-FAQ alignment and topic clustering.
- Gap engine: missing / thin / unique / FAQ / internal-link / example / quality gaps with priority scoring.
- `build_report.py` — generates a self-contained visual HTML report (KPI cards, cluster matrix, SVG charts, filterable gap table) and an XLSX workbook (KPI filters, multi-sheet); CSV fallback if `openpyxl` is absent.
- Blocked-site fallback chain: WebFetch → local `requests` (browser headers) → manual paste.
- Guardrail: identifies gaps and produces content briefs/outlines/checklists — never the finished copy.
