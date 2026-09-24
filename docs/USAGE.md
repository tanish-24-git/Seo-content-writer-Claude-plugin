# Using the SEO Content-Gap Analyzer (for content writers)

A simple, non-technical guide. You do **not** need to know any code.

## 1. One-time setup (your tech lead does this once)
Install Claude Code and log in, then in a Claude session:
```
/plugin marketplace add tanish-24-git/Seo-content-writer-Claude-plugin
/plugin install seo-content-gap@seo-content-gap-marketplace
```
*(Optional, for the Excel report)* install Python and run `pip install openpyxl`. If you skip
this, you still get the HTML report and CSV files. The PDF is printed automatically if Chrome or
Edge is installed.

*(Optional, for page speed and authority data)* PageSpeed Insights works with no setup; a
`PSI_API_KEY` raises Google's quota. For Ahrefs data, either set `AHREFS_API_KEY` or connect the
Ahrefs connector in Claude — the tool says roughly how many Ahrefs units a run uses before fetching.

## 2. Run an analysis
Open a terminal in a **neutral folder** (a fresh content-work folder — *not* inside another
company's codebase, so no outside context leaks in), then:
```
mkdir seo-gap-work && cd seo-gap-work
claude
> /seo-gap https://www.example.com/your-page
```
It will ask you:
1. **Is this the right page and topic?** (it guesses the page type — confirm or correct.)
2. **Competitor URLs?** Paste as many as you want, one per line — **or just press Enter** and
   it finds the top-ranking competitors for you.

Then it crawls everything and tells you, among other things, **whether your page ranks** for the
topic and where.

## 3. What you get (in `./content-gap-runs/<topic>/`)
- **`report.html`** — the full report. Double-click to open in a browser; use the menu on the
  left to jump between sections, and the filters to show only what your page is missing.
- **`report.pdf`** — the same report as a document to share.
- **`report.xlsx`** — Excel, one sheet per section, with filters.
- **`report.md`** — a plain readable summary.

The report covers: an **executive summary**, **page speed & Core Web Vitals** (mobile and
desktop), **technical SEO checks**, **keywords** (where the target phrase appears, and what each
page ranks for), **authority** (backlinks, ratings), the **H1–H4 heading hierarchy** (which
headings each page has), **topic coverage** (who covers each topic, under which heading level,
how deeply), the **exact content** each page wrote per topic, **FAQs** word for word, **links and
images**, and **recommendations**. Anything that was not measured says "Not available yet".

## 4. Then just chat
After the report, keep typing questions:
- `what's missing vs the top 3 competitors?`
- `show only the FAQ gaps`
- `which internal links should I add?`
- `compare everyone's "how much cover" section`
- `are they following SEO guidelines?`
- `give me a content brief for the weakest cluster`
- `re-run for https://www.example.com/another-page`

It answers from the analysis it just did. When you ask for a **brief**, it gives you a
**structure + must-cover points + which competitor to study** — **it will not write the final
article**. That part is yours; this tool just makes it fast.

## 5. Recommended permissions (smoother experience)
The first run will ask permission to use web/search/file tools. To avoid repeat prompts, your
tech lead can add this to their Claude settings (`~/.claude/settings.json` or project
`.claude/settings.json`):
```json
{ "permissions": { "allow": [
  "WebFetch", "WebSearch", "Read", "Write", "Glob", "Grep",
  "Bash(python:*)", "Bash(python3:*)"
] } }
```

## 6. Troubleshooting
- **"A site is blocked / 403."** Some sites (often big banks/insurers) block automated reading.
  The tool will tell you and offer to continue without it, or you can **paste that page's text**
  when asked and it will include it.
- **No Excel file, only CSVs.** Install `openpyxl` (`pip install openpyxl`) and re-run.
- **No PDF?** Install Chrome or Edge (or set `SEO_GAP_BROWSER` to its path) and re-run — or open
  `report.html` → Print → Save as PDF.
- **Page speed says "Not measured" / HTTP 429.** Google rate-limits keyless requests; set
  `PSI_API_KEY` and re-run.
- **It refused to write the article.** That's by design — it's a gap-finder, not a copywriter.
