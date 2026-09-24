# SEO Content-Gap Analyzer — Claude Code Plugin

A Claude Code plugin that helps an SEO/content team **write better pages, faster**, by
showing **exactly where their page falls short of the competition** — block-to-block,
FAQ-to-FAQ, cluster-by-cluster — and then letting them **interrogate the gaps in a
conversational session**.

It is **page-level** (you analyze one page at a time, e.g. a "term plan" page), **generic**
(built for fintech/insurance SEO teams; not tied to any single brand), and it **does not
write the final copy** — it surfaces gaps, clusters, quality differences, internal-linking
deltas, and content briefs so a human writer can move quickly.

---

## What it does

1. **You give it your page URL** (the page you want to write/improve).
2. **You add competitor URLs** — as many as you like — **or leave them blank** and Claude
   web-searches the top-ranking competitor pages for that topic.
3. It **checks search ranking** for the topic and tells you **which pages rank** — and
   **whether *your* page is in the ranking** (and at what position).
4. It **crawls every page** and extracts a structured map: headings, every section's content,
   FAQs, examples/numbers, internal links, tables, schema, author/reviewer, word counts.
5. It **aligns them block-to-block and FAQ-to-FAQ** and groups everything into **topic
   clusters** so you can see — for each idea — what each competitor wrote, how they wrote it,
   whether everyone wrote the same thing, and what extra each one has.
6. It computes **gaps** (missing / thin / unique / FAQ / internal-link / example / quality)
   with **priority scores**, plus **content-quality** signals (depth, examples, schema,
   E-E-A-T author/reviewer, freshness, readability) and whether pages follow SEO guidelines.
7. It measures **page speed & Core Web Vitals** for every page (Google PageSpeed Insights —
   real-user CrUX data + Lighthouse, mobile and desktop) and, when Ahrefs is available,
   **authority & visibility** (URL/Domain Rating, backlinks, referring domains, ranking keywords).
8. It generates the report in **three formats**, same content in each:
   - **`report.html`** — the full report: executive summary, page speed, technical SEO,
     keywords, authority, the H1–H4 heading hierarchy (present or not per page), topic coverage
     with the heading level each page used, the exact content per topic, FAQs verbatim, links,
     images, and recommendations — with filters and search.
   - **`report.pdf`** — the same report, printed automatically with your installed Chrome/Edge.
   - **`report.xlsx`** — one sheet per section plus full-detail sheets.
   - (plus **`report.md`**, a readable text summary)
9. It then stays **conversational** — ask it anything about the gaps and get **content
   briefs / outlines / checklists** (never finished prose).

---

## Install (one-time)

> Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and
> authenticated. The report scripts use Python 3; the XLSX needs `openpyxl` (the plugin
> degrades to CSV if it's missing) and the PDF needs Chrome or Edge installed.
>
> Optional data sources:
> - **PageSpeed Insights** is free and works without a key; set `PSI_API_KEY` (or
>   `PSI_SERVICE_ACCOUNT_JSON` + `pip install google-auth`) for a higher quota.
> - **Ahrefs** uses `AHREFS_API_KEY`, or a connected Ahrefs connector in Claude. Without either,
>   the authority sections show "Not available yet".

In a Claude Code session:

```
/plugin marketplace add tanish-24-git/Seo-content-writer-Claude-plugin
/plugin install seo-content-gap@seo-content-gap-marketplace
```

(For an internal/private host, replace the first argument with your git URL or a local path.)

## Use (daily)

```
cd <a-folder-where-you-keep-content-work>
claude
> /seo-gap https://www.example.com/your-term-plan-page
#   → it guides you: add competitor URLs (or press Enter to auto-discover)
#   → crawl → align → cluster → page speed + authority → report (HTML + PDF + XLSX)
#   → then just chat:
> what's missing vs the top 3 competitors?
> show only the FAQ gaps
> which internal links should I add?
> give me a content brief for the weakest cluster
```

Run outputs are written to `./content-gap-runs/<topic-slug>/` in your current folder.

See **[docs/USAGE.md](docs/USAGE.md)** for a non-technical walkthrough and
**[docs/FLOW.md](docs/FLOW.md)** for the full flow.

---

## Repository layout

```
.claude-plugin/marketplace.json     marketplace manifest (enables /plugin install)
plugins/seo-content-gap/            the plugin
  .claude-plugin/plugin.json        plugin manifest
  commands/                         /seo-gap and /seo-gap-help
  agents/                           page-extractor, competitor-finder, gap-analyst
  skills/seo-content-gap/SKILL.md   the orchestrator + conversation rules
  skills/.../reference/             extraction schema, gap rubric, brief template, QA checklist
  scripts/build_report.py           run JSON → report.html + report.pdf + report.xlsx
  scripts/report_*.py               data layer and HTML / XLSX / PDF renderers
  scripts/fetch_pagespeed.py        Core Web Vitals via Google PageSpeed Insights → pagespeed.json
  scripts/fetch_ahrefs.py           authority + keywords via Ahrefs → authority.json
docs/                               USAGE.md, FLOW.md, examples/
```

## Privacy & safety
- The plugin is **generic** — it contains no client names or proprietary logic.
- It **does not generate publishable content** — only gaps, briefs, outlines, and checklists.
- The hardened `.gitignore` ensures **run outputs, databases, and secrets are never committed**.
- `WebFetch`/`WebSearch` run server-side via Anthropic, so the core crawl works even on
  locked-down corporate networks; a `requests` fallback and manual-paste handle bot-blocked sites.

## License
MIT — see [LICENSE](LICENSE).
