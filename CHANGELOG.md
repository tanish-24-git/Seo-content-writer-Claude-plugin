# Changelog

All notable changes to the SEO Content-Gap plugin are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.4.0] — 2026-06-03
### Added
- **Full page structure** section (HTML + PDF): per-company dropdown reproducing each page as
  published — `H1`/`H2`/`H3` tag + heading + the copy beneath it, in document order, your page
  first. New **Page Structure** XLSX sheet (Page · Order · Tag · Heading · Words · Content). Print
  now expands all dropdowns so they appear in the Save-as-PDF output.
- **Unique coverage** view — topics that exactly ONE compared page covers (per-company unique
  angle), as an HTML table + **Unique Coverage** XLSX sheet. gap-analyst now emits single-brand
  clusters so unique topics are never dropped.
- **Pages analysed — title & H1** table (page `<title>` + `<h1>` + URL per company) + **Page
  Titles & H1** XLSX sheet.
- **Topic coverage per company** — per-company dropdown of covered topics with depth, the heading
  on their page, and a deep-link that opens that exact section live; **Topic Coverage** XLSX sheet.
### Changed
- **Internal links are now on-page only** — nav, header and footer boilerplate is excluded
  everywhere (counts, charts, tables, XLSX) and at the extraction source (`extract_page.py`), so
  the gap analysis reflects real in-content linking. (e.g. a page with 500 raw internal links but
  475 in nav now reports 12 on-page.) Detection keys off semantic `<nav>/<header>/<footer>/<aside>`.

## [0.3.1] — 2026-06-02
### Fixed
- **Your-brand column rendered all zeros** when clusters.json keyed a page under a non-canonical
  name (e.g. `"OUR PAGE"`). Fixed in both layers: gap-analyst now mandates exact `meta.json`
  brand keys (examples no longer show `"OUR PAGE"`) and the orchestrator echoes the canonical
  brand list into the agent; `build_report.py` resolves brand keys case/whitespace-insensitively,
  warns loudly on any unmatched canonical brand in a populated cluster, and fails the build if the
  your-brand column is entirely zero (almost always a key mismatch, not a real result).

## [0.3.0] — 2026-06-02
### Added — "show the real content, not just a score"
- `extract_page.py` now also captures the **actual body text under every heading** (`sections[].text`)
  and **every image** (src + alt), plus a separate **external_links** list.
- Report shows, per topic cluster, a **side-by-side of what each page actually wrote** (real text
  excerpts), each with its **depth**, a **deep-link that opens that exact section on the live page**
  (Chrome text-fragment), and an in-report anchor (click a cluster in the map to jump to it).
- **Content-similarity scoring** (difflib): for each cluster it reports how similar the wording is
  across pages (near-duplicate / reworded / distinct) — answers "is everyone's content the same?".
- **Ranking view** per page: how a Google search crawler and an AI answer engine would likely
  treat/cite it. **External-brand mentions** per page (which third parties each page names).
- XLSX is now the full content workbook: **Full Content** (every section + text), **Section
  Comparison** (per cluster, each page's text + similarity-to-ours), separate **H1 / H2 / H3**
  sheets, **Internal Links**, **External Links**, **Images**, **Ranking View**, **External Brands**,
  plus Gaps / FAQ / Quality — all filterable, wrapped text.
### Changed
- gap-analyst emits `ranking_assessment` + `external_brands`; build_report pulls verbatim section
  text from the page JSONs and computes similarity deterministically.

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
