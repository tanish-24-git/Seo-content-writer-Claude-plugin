# Using the SEO Content-Gap Analyzer (for content writers)

A simple, non-technical guide. You do **not** need to know any code.

## 1. One-time setup (your tech lead does this once)
Install Claude Code and log in, then in a Claude session:
```
/plugin marketplace add tanish-24-git/Seo-content-writer-Claude-plugin
/plugin install seo-content-gap@seo-content-gap-marketplace
```
*(Optional, for the Excel report)* install Python and run `pip install openpyxl`. If you skip
this, you still get the HTML report and CSV files.

## 2. Run an analysis
Open a terminal in any folder where you keep content work, then:
```
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
- **`report.html`** — the visual report. Double-click to open in a browser. To share as PDF:
  **File → Print → Save as PDF**.
- **`report.xlsx`** — Excel with filters (sort/slice the gaps, clusters, FAQs, links by priority).
- **`report.md`** — a plain readable version.

The report shows: a **cluster matrix** (every topic × every competitor, who covered what and how
deeply), **prioritised gaps** (what to add / expand), **FAQ gaps**, **internal-link gaps**, and a
**content-quality table** (word count, examples, schema, author/reviewer, freshness).

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
- **PDF?** Open `report.html` → Print → Save as PDF (works on any machine, no extra software).
- **It refused to write the article.** That's by design — it's a gap-finder, not a copywriter.
