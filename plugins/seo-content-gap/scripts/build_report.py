#!/usr/bin/env python3
"""Build the visual report for a content-gap run.

Input : a run directory containing meta.json, clusters.json, gaps.json and the
        per-page block JSONs (our.json + competitor-*.json).
Output: report.html  (self-contained: KPI cards, cluster matrix, SVG charts,
                      filterable gap table — open in a browser, Print -> Save as PDF)
        report.xlsx  (multi-sheet, KPI auto-filters) if `openpyxl` is installed,
                      else gaps.csv / clusters.csv / quality.csv as a fallback.

No third-party dependency is required for the HTML (charts are hand-rolled SVG,
no CDN — works offline and on locked-down networks). XLSX needs `openpyxl`.

Usage: python build_report.py <run_dir>
"""
import csv
import html
import json
import os
import sys


# ----------------------------- load -----------------------------------------
def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def load_run(run_dir):
    meta = _load(os.path.join(run_dir, "meta.json"), {})
    clusters = _load(os.path.join(run_dir, "clusters.json"), {"clusters": []})
    gaps = _load(os.path.join(run_dir, "gaps.json"), {})
    pages = []
    for name in sorted(os.listdir(run_dir)):
        if name.endswith(".json") and (name == "our.json" or name.startswith("competitor")):
            pages.append(_load(os.path.join(run_dir, name), {}))
    return meta, clusters, gaps, pages


def brand_order(meta, gaps, pages):
    your = gaps.get("your_brand") or meta.get("your_brand") or "OUR PAGE"
    order = [your]
    for p in pages:
        b = p.get("brand")
        if b and b not in order:
            order.append(b)
    for b in gaps.get("competitors", []):
        if b not in order:
            order.append(b)
    return your, order


# ----------------------------- svg chart ------------------------------------
def svg_bar(title, pairs, unit=""):
    pairs = [(str(l), float(v or 0)) for l, v in pairs]
    if not pairs:
        return ""
    mx = max((v for _, v in pairs), default=0) or 1
    bar_h, gap, left, top, width = 22, 10, 160, 30, 520
    height = top + len(pairs) * (bar_h + gap) + 10
    rows = []
    for i, (label, val) in enumerate(pairs):
        y = top + i * (bar_h + gap)
        w = int((val / mx) * (width - left - 70))
        rows.append(
            f'<text x="0" y="{y + 15}" class="lbl">{html.escape(label[:24])}</text>'
            f'<rect x="{left}" y="{y}" width="{max(w,1)}" height="{bar_h}" rx="3" class="bar"/>'
            f'<text x="{left + max(w,1) + 6}" y="{y + 15}" class="val">{val:g}{unit}</text>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">'
        f'<text x="0" y="16" class="ctitle">{html.escape(title)}</text>'
        + "".join(rows)
        + "</svg>"
    )


# ----------------------------- html -----------------------------------------
CSS = """
*{box-sizing:border-box} body{font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;
 color:#0f172a;max-width:1100px;margin:0 auto;padding:16px 28px;line-height:1.5}
h1{font-size:24px;border-bottom:3px solid #1e3a8a;padding-bottom:6px;color:#1e3a8a}
h2{font-size:18px;margin-top:28px;border-bottom:1px solid #cbd5e1;padding-bottom:4px;color:#1e3a8a}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.kpi{flex:1 1 150px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px}
.kpi .n{font-size:26px;font-weight:700;color:#1e3a8a} .kpi .l{font-size:12px;color:#475569}
.banner{padding:10px 14px;border-radius:8px;margin:8px 0;font-size:14px}
.ok{background:#dcfce7;border:1px solid #16a34a;color:#166534}
.warn{background:#fef3c7;border:1px solid #f59e0b;color:#92400e}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
th,td{border:1px solid #cbd5e1;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#eef2ff} .matrix td{text-align:center;font-weight:600}
.d0{background:#fee2e2;color:#991b1b}.d1{background:#fef3c7}.d2{background:#dbeafe}.d3{background:#dcfce7;color:#166534}
.p3{color:#b91c1c;font-weight:700}.p2{color:#b45309;font-weight:600}.p1{color:#1d4ed8}
.chart{width:100%;max-width:560px;margin:6px 0}
.chart .ctitle{font-size:13px;font-weight:700;fill:#1e3a8a}.chart .lbl{font-size:11px;fill:#334155}
.chart .val{font-size:11px;fill:#475569}.chart .bar{fill:#3b82f6}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.controls input,.controls select{padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px}
.charts{display:flex;flex-wrap:wrap;gap:24px}
small{color:#64748b} code{background:#f1f5f9;padding:1px 5px;border-radius:4px}
@media print{.controls{display:none}}
"""

FILTER_JS = """
function f(){var q=(document.getElementById('q').value||'').toLowerCase();
var t=document.getElementById('ft').value,p=document.getElementById('fp').value;
document.querySelectorAll('#gaps tbody tr').forEach(function(r){
 var okq=r.innerText.toLowerCase().indexOf(q)>=0;
 var okt=!t||r.dataset.type===t; var okp=!p||r.dataset.prio===p;
 r.style.display=(okq&&okt&&okp)?'':'none';});}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def build_html(run_dir, meta, clusters, gaps, pages, your, order):
    k = gaps.get("kpis", {})
    serp = gaps.get("serp", {})
    topic = esc(gaps.get("topic") or meta.get("topic") or "this page")
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           f"<title>Content-Gap Report — {topic}</title><style>{CSS}</style></head><body>"]
    out.append(f"<h1>Content-Gap Report — {topic}</h1>")
    out.append(f"<small>Your page: <code>{esc(gaps.get('your_url') or meta.get('your_url'))}</code> · "
               f"page type: <b>{esc(gaps.get('page_type') or meta.get('page_type'))}</b> · "
               f"competitors: {len(order)-1}</small>")

    # ranking banner
    yr = serp.get("your_rank")
    if yr:
        out.append(f"<div class='banner ok'>✅ Your page ranks <b>#{esc(yr)}</b> for "
                   f"\"{esc(serp.get('query'))}\".</div>")
    else:
        out.append("<div class='banner warn'>⚠️ Your page did <b>not</b> appear in the top "
                   "search results for this topic — a visibility gap to close.</div>")

    # KPI cards
    cards = [("coverage_pct", "Topic coverage", "%"), ("missing_count", "Missing sections", ""),
             ("thin_count", "Thin sections", ""), ("faq_gap_count", "FAQ gaps", ""),
             ("link_gap_count", "Internal-link gaps", ""), ("quality_score", "Quality score", "")]
    out.append("<div class='kpis'>")
    for key, label, unit in cards:
        out.append(f"<div class='kpi'><div class='n'>{esc(k.get(key,0))}{unit}</div>"
                   f"<div class='l'>{label}</div></div>")
    out.append("</div>")

    # cluster matrix
    out.append("<h2>Cluster coverage — who wrote what</h2>")
    out.append("<small>0 = absent · 1 = mention · 2 = standard · 3 = deep (example/table)</small>")
    out.append("<table class='matrix'><thead><tr><th style='text-align:left'>Topic cluster</th>")
    for b in order:
        out.append(f"<th>{esc(b)}</th>")
    out.append("</tr></thead><tbody>")
    for c in clusters.get("clusters", []):
        out.append(f"<tr><td style='text-align:left'>{esc(c.get('name'))}</td>")
        for b in order:
            info = (c.get("brands") or {}).get(b, {})
            d = int(info.get("depth", 0) or 0)
            out.append(f"<td class='d{d}' title='{esc(info.get('snippet',''))}'>{d}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")

    # charts
    out.append("<h2>How the pages compare</h2><div class='charts'>")
    out.append(svg_bar("Total word count", [(p.get("brand", "?"), p.get("word_count_total", 0)) for p in pages]))
    out.append(svg_bar("Sections", [(p.get("brand", "?"), len(p.get("sections", []))) for p in pages]))
    out.append(svg_bar("FAQs answered", [(p.get("brand", "?"), len(p.get("faqs", []))) for p in pages]))
    out.append(svg_bar("Internal links", [(p.get("brand", "?"), len(p.get("internal_links", []))) for p in pages]))
    out.append("</div>")

    # gaps table (filterable)
    out.append("<h2>Prioritised gaps</h2>")
    out.append("<div class='controls'><input id='q' onkeyup='f()' placeholder='search gaps…'>"
               "<select id='ft' onchange='f()'><option value=''>all types</option>"
               "<option>missing</option><option>thin</option><option>unique</option>"
               "<option>faq</option><option>link</option><option>example</option><option>quality</option></select>"
               "<select id='fp' onchange='f()'><option value=''>all priorities</option>"
               "<option value='3'>P3</option><option value='2'>P2</option><option value='1'>P1</option></select></div>")
    out.append("<table id='gaps'><thead><tr><th>P</th><th>Type</th><th>Cluster</th><th>What to do</th><th>Exemplar</th></tr></thead><tbody>")
    for g in sorted(gaps.get("gaps", []), key=lambda x: -int(x.get("priority", 0) or 0)):
        pr = int(g.get("priority", 0) or 0)
        out.append(f"<tr data-type='{esc(g.get('type'))}' data-prio='{pr}'>"
                   f"<td class='p{pr}'>P{pr}</td><td>{esc(g.get('type'))}</td>"
                   f"<td>{esc(g.get('cluster'))}</td>"
                   f"<td><b>{esc(g.get('title'))}</b><br><small>{esc(g.get('recommendation') or g.get('detail'))}</small></td>"
                   f"<td>{esc(g.get('exemplar_brand'))}</td></tr>")
    out.append("</tbody></table>")

    # faq + link gaps
    fg = gaps.get("faq_gaps", [])
    if fg:
        out.append("<h2>FAQ gaps (questions competitors answer, you don't)</h2><ul>")
        for q in fg:
            out.append(f"<li>{esc(q.get('question'))} <small>— answered by {esc(', '.join(q.get('answered_by', [])))}</small></li>")
        out.append("</ul>")
    lg = gaps.get("link_gaps", [])
    if lg:
        out.append("<h2>Internal-link gaps</h2><ul>")
        for l in lg:
            out.append(f"<li>{esc(l.get('topic_or_target'))} <small>— linked by {esc(', '.join(l.get('present_in', [])))}</small></li>")
        out.append("</ul>")

    # quality table
    q = (gaps.get("quality") or {}).get("per_brand", {})
    if q:
        out.append("<h2>Content-quality signals</h2><table><thead><tr><th>Brand</th><th>Words</th>"
                   "<th>Sections</th><th>FAQs</th><th>Int. links</th><th>Schema</th><th>E-E-A-T</th><th>Freshness</th></tr></thead><tbody>")
        for b in order:
            r = q.get(b, {})
            out.append(f"<tr><td>{esc(b)}</td><td>{esc(r.get('word_count'))}</td><td>{esc(r.get('sections'))}</td>"
                       f"<td>{esc(r.get('faqs'))}</td><td>{esc(r.get('internal_links'))}</td>"
                       f"<td>{esc(', '.join(r.get('schema', []) or []))}</td>"
                       f"<td>{'yes' if r.get('eeat') else 'no'}</td><td>{esc(r.get('freshness'))}</td></tr>")
        out.append("</tbody></table>")

    out.append("<hr><small>Generated by the SEO Content-Gap Analyzer. This report identifies gaps "
               "and briefs — it does not contain publishable copy. Verify any figure against the live "
               "pages before using.</small>")
    out.append(f"<script>{FILTER_JS}</script></body></html>")
    path = os.path.join(run_dir, "report.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return path


# ----------------------------- xlsx / csv ------------------------------------
def build_xlsx(run_dir, meta, clusters, gaps, pages, your, order):
    try:
        from openpyxl import Workbook
        from openpyxl.chart import BarChart, Reference
        from openpyxl.styles import Font, PatternFill
    except Exception:
        # fallback: CSVs
        with open(os.path.join(run_dir, "gaps.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["priority", "type", "cluster", "title", "recommendation", "exemplar"])
            for g in gaps.get("gaps", []):
                w.writerow([g.get("priority"), g.get("type"), g.get("cluster"),
                            g.get("title"), g.get("recommendation") or g.get("detail"), g.get("exemplar_brand")])
        return None, "openpyxl not installed — wrote gaps.csv instead (pip install openpyxl for the XLSX)."

    wb = Workbook()
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1E3A8A")

    def hdr(ws, cols):
        ws.append(cols)
        for c in ws[1]:
            c.font = head
            c.fill = fill

    # Overview
    ws = wb.active
    ws.title = "Overview"
    k = gaps.get("kpis", {})
    hdr(ws, ["KPI", "Value"])
    for label, key in [("Topic coverage %", "coverage_pct"), ("Missing sections", "missing_count"),
                       ("Thin sections", "thin_count"), ("Unique sections", "unique_count"),
                       ("FAQ gaps", "faq_gap_count"), ("Internal-link gaps", "link_gap_count"),
                       ("Example gaps", "example_gap_count"), ("Quality score", "quality_score"),
                       ("Your word count", "your_word_count"), ("Competitor median words", "competitor_median_word_count")]:
        ws.append([label, k.get(key, 0)])

    # Word-count chart from a small data block
    ws.append([]); ws.append(["Brand", "Words"])
    start = ws.max_row
    for p in pages:
        ws.append([p.get("brand", "?"), p.get("word_count_total", 0)])
    chart = BarChart(); chart.title = "Total word count by page"; chart.type = "bar"
    data = Reference(ws, min_col=2, min_row=start, max_row=ws.max_row)
    cats = Reference(ws, min_col=1, min_row=start + 1, max_row=ws.max_row)
    chart.add_data(data, titles_from_data=True); chart.set_categories(cats)
    ws.add_chart(chart, "D2")

    # Cluster matrix
    ws = wb.create_sheet("Cluster Matrix")
    hdr(ws, ["Cluster"] + order)
    for c in clusters.get("clusters", []):
        row = [c.get("name")]
        for b in order:
            row.append(int((c.get("brands") or {}).get(b, {}).get("depth", 0) or 0))
        ws.append(row)
    ws.auto_filter.ref = ws.dimensions

    # Gaps (filterable)
    ws = wb.create_sheet("Gaps")
    hdr(ws, ["Priority", "Type", "Cluster", "Title", "Recommendation", "Exemplar"])
    pr_fill = {3: PatternFill("solid", fgColor="FECACA"),
               2: PatternFill("solid", fgColor="FEF3C7"),
               1: PatternFill("solid", fgColor="DBEAFE")}
    for g in sorted(gaps.get("gaps", []), key=lambda x: -int(x.get("priority", 0) or 0)):
        ws.append([g.get("priority"), g.get("type"), g.get("cluster"), g.get("title"),
                   g.get("recommendation") or g.get("detail"), g.get("exemplar_brand")])
        f = pr_fill.get(int(g.get("priority", 0) or 0))
        if f:
            ws.cell(row=ws.max_row, column=1).fill = f
    ws.auto_filter.ref = ws.dimensions

    # FAQ gaps
    ws = wb.create_sheet("FAQ Gaps")
    hdr(ws, ["Question", "Answered by"])
    for q in gaps.get("faq_gaps", []):
        ws.append([q.get("question"), ", ".join(q.get("answered_by", []))])
    ws.auto_filter.ref = ws.dimensions

    # Link gaps
    ws = wb.create_sheet("Link Gaps")
    hdr(ws, ["Topic / target", "Linked by"])
    for l in gaps.get("link_gaps", []):
        ws.append([l.get("topic_or_target"), ", ".join(l.get("present_in", []))])
    ws.auto_filter.ref = ws.dimensions

    # Quality
    ws = wb.create_sheet("Quality")
    hdr(ws, ["Brand", "Words", "Sections", "FAQs", "Internal links", "Schema", "E-E-A-T", "Freshness"])
    q = (gaps.get("quality") or {}).get("per_brand", {})
    for b in order:
        r = q.get(b, {})
        ws.append([b, r.get("word_count"), r.get("sections"), r.get("faqs"),
                   r.get("internal_links"), ", ".join(r.get("schema", []) or []),
                   "yes" if r.get("eeat") else "no", r.get("freshness")])
    ws.auto_filter.ref = ws.dimensions

    path = os.path.join(run_dir, "report.xlsx")
    wb.save(path)
    return path, None


# ----------------------------- main ------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("usage: python build_report.py <run_dir>"); sys.exit(1)
    run_dir = sys.argv[1]
    if not os.path.isdir(run_dir):
        print("run_dir not found:", run_dir); sys.exit(1)
    meta, clusters, gaps, pages = load_run(run_dir)
    your, order = brand_order(meta, gaps, pages)
    html_path = build_html(run_dir, meta, clusters, gaps, pages, your, order)
    print("HTML  ->", html_path)
    xlsx_path, note = build_xlsx(run_dir, meta, clusters, gaps, pages, your, order)
    if xlsx_path:
        print("XLSX  ->", xlsx_path)
    if note:
        print("NOTE :", note)
    print("Open report.html in a browser and Print -> Save as PDF for a shareable PDF.")


if __name__ == "__main__":
    main()
