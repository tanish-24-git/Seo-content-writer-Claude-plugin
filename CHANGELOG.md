# Changelog

All notable changes to the SEO Content-Gap plugin are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-06-02
### Added
- `scripts/extract_page.py` — deterministic, standard-library HTML parser that extracts the
  **exact** title/meta/H1, full H1–H6 outline, and **every internal/external link** (anchor +
  target + section + scope) straight from the raw HTML. Fixes inaccurate ("fake") internal-link
  data that came from summarised markdown.
- Report now shows, per page: the **H1/H2/H3 outline** and a **real internal-link table**
  (anchor → target → section → scope) — Content Writer v2 quality. New XLSX sheets:
  **Page Structure** and **Internal Links** (both filterable).
### Changed
- `page-extractor` agent runs `extract_page.py` first for accurate structure/links, then layers
  semantic summaries/FAQs via WebFetch.
- Block schema enriched: `heading_counts`, `heading_outline`, detailed `internal_links`,
  `unique_internal_targets`, `external_link_count`, `image_count`.
- Hardened the **brand-blind** rule: the skill never infers/pre-fills a company name or URL from
  surrounding context; always asks the user; refer to pages by domain only.
- `_load` is BOM-tolerant.

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
