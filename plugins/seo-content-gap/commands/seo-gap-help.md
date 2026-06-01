---
description: How to use the SEO Content-Gap Analyzer.
---

Show the user this help, in a friendly, non-technical tone:

# `/seo-gap` — quick help

**What it does:** compares ONE of your pages against competitor pages and shows you exactly
what to write, expand, or add — then you can chat with it about the gaps.

**How to start:**
- `/seo-gap https://www.example.com/your-page` — start with your page URL, or
- `/seo-gap` — and it will ask you for the URL.

**What it will ask you:**
1. **Your page URL** — the page you want to improve (e.g. your "term plan" page).
2. **Competitor URLs** — paste as many as you want (one per line). **Or press Enter** and it
   will web-search the top-ranking competitor pages for that topic automatically.
   - It compares **like-for-like**: product↔product, blog↔blog, FAQ↔FAQ.
   - It tells you **who ranks** for the topic — and **whether your page ranks**, and where.

**What you get:**
- A **visual report** (`report.html` → print to PDF), an **Excel** workbook with KPI filters
  (`report.xlsx`), and a readable `report.md`, all under `./content-gap-runs/<topic>/`.
- **Clusters** (same topic, every brand side by side), **gaps** (missing / thin / unique /
  FAQ / internal-link / example / quality), and **content briefs**.

**Then just chat, e.g.:**
- "what's missing vs the top 3 competitors?"
- "show only the FAQ gaps"
- "which internal links should I add?"
- "give me a content brief for the weakest cluster"
- "re-run for my <other> page"

**Note:** this tool **finds gaps and writes briefs — it never writes the final article**.
That's your job; this just makes it fast.
