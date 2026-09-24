#!/usr/bin/env python3
"""Build the content-gap report for a run: report.html, report.pdf, report.xlsx.

    python build_report.py <run_dir> [--out DIR] [--no-pdf]

Reads the run directory — meta.json, clusters.json, gaps.json, our.json,
competitor-*.json, and when present ranking.json, pagespeed.json
(fetch_pagespeed.py) and authority.json (fetch_ahrefs.py) — and writes:

  report.html  professional, self-contained page: executive summary, page speed
               & Core Web Vitals, technical / on-page SEO, keywords, visibility &
               authority, H1-H4 heading hierarchy, topic coverage & gaps, exact
               content by topic, FAQs, links & images, recommendations, sources.
  report.pdf   the same report printed via local Chrome/Edge (collapsed detail
               expanded; raw link/image dumps left to the HTML and XLSX).
  report.xlsx  one sheet per section plus full-detail sheets
               (CSV fallback if openpyxl is missing).

Sections whose data source was not run (PageSpeed, Ahrefs) render as
"Not available yet". Standard library only, except openpyxl for XLSX.
"""
import argparse
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_core import *  # noqa: F401,F403  (re-exported for callers that import build_report)
from report_core import assert_your_column, build_context, check_brand_keys
import report_html
import report_pdf
import report_xlsx


def write_csv_fallback(ctx, out_dir):
    order = ctx["order"]
    with open(os.path.join(out_dir, "topic_coverage.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Topic"] + order)
        for t in ctx["topics"]:
            w.writerow([t["name"]] + [t["brands"][b]["tag"] or "-" for b in order])
    with open(os.path.join(out_dir, "faq_coverage.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Question"] + order)
        for r in ctx["faq_rows"]:
            w.writerow([r["question"]] + ["Yes" if r["present"][b] else "No" for b in order])
    with open(os.path.join(out_dir, "heading_hierarchy.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Level", "Heading"] + order)
        for r in ctx["tree"]:
            w.writerow([f'H{r["level"]}', r["text"]] + ["Yes" if r["present"][b] else "No" for b in order])


def main():
    ap = argparse.ArgumentParser(description="Build report.html / report.pdf / report.xlsx for a content-gap run.")
    ap.add_argument("run_dir")
    ap.add_argument("--out", help="output folder (default: the run folder)")
    ap.add_argument("--no-pdf", action="store_true", help="skip the PDF")
    a = ap.parse_args()
    if not os.path.isdir(a.run_dir):
        print("run_dir not found:", a.run_dir)
        return 1
    out = a.out or a.run_dir
    os.makedirs(out, exist_ok=True)

    ctx = build_context(a.run_dir)
    # Loud warnings BEFORE building — a canonical brand that resolves to no key in
    # a populated cluster would otherwise ship as an empty column.
    for w in check_brand_keys(ctx["clusters"], ctx["order"]):
        print("WARN :", w, file=sys.stderr)
    for name, doc in (("pagespeed.json", ctx["psi"]), ("authority.json", ctx["auth"])):
        print(f"DATA : {name} {'found' if doc else 'not found — section shows Not available yet'}")

    html_path = os.path.join(out, "report.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(report_html.render(ctx))
    print("HTML ->", html_path)

    if not a.no_pdf:
        tmp = os.path.join(out, ".report_print.html")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(report_html.render(ctx, print_mode=True))
        ok, msg = report_pdf.html_to_pdf(tmp, os.path.join(out, "report.pdf"))
        try:
            os.remove(tmp)
        except OSError:
            pass
        print(("PDF  -> " if ok else "PDF  : skipped — ") + msg)

    try:
        xlsx = report_xlsx.render(ctx, os.path.join(out, "report.xlsx"))
    except PermissionError:
        # Usually the previous report.xlsx is open in Excel (Windows locks it).
        alt = os.path.join(out, "report-%s.xlsx" % datetime.now().strftime("%Y%m%d-%H%M%S"))
        print("NOTE : report.xlsx is open in another program — saving as", os.path.basename(alt))
        xlsx = report_xlsx.render(ctx, alt)
    if xlsx:
        print("XLSX ->", xlsx)
    else:
        write_csv_fallback(ctx, out)
        print("NOTE : openpyxl not installed — wrote topic_coverage.csv, faq_coverage.csv, heading_hierarchy.csv "
              "(pip install openpyxl for the full workbook)")

    # Post-build assertion: a fully-zero your-brand column is a key mismatch.
    assert_your_column(ctx["clusters"], ctx["your"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
