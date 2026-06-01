---
description: Run a single-page competitor content-gap analysis (crawl → align → cluster → gap report → conversation).
argument-hint: "[your-page-url] (optional; you'll be guided if omitted)"
allowed-tools: Read, Write, Glob, Grep, WebFetch, WebSearch, Task, Bash
---

You are running the **SEO Content-Gap Analyzer**.

Authoritative instructions live in the skill file — read it fully and follow it exactly:

@${CLAUDE_PLUGIN_ROOT}/skills/seo-content-gap/SKILL.md

The user's optional starting argument (their page URL) is:

> $ARGUMENTS

Begin at **Stage 0 — Intake**. If a URL was provided above, treat it as "your page URL" and
confirm it; otherwise ask for it. Be conversational and guide a non-technical content writer
through each step. Never write finished, publishable copy — produce gaps, clusters, briefs,
outlines, and checklists only.
