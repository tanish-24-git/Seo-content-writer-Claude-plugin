#!/usr/bin/env python3
"""Build the visual report for a content-gap run.

Input : a run directory containing meta.json, clusters.json, gaps.json and the
        per-page block JSONs (our.json + competitor-*.json), each with accurate
        heading_outline + internal_links (from extract_page.py).
Output: report.html  (KPI cards, cluster matrix, SVG charts, per-page H1/H2/H3
                      outline, real internal-link tables, filterable gap table.
                      Open in a browser, Print -> Save as PDF)
        report.xlsx  (Overview/KPIs, Cluster Matrix, Page Structure, Internal Links,
                      Gaps, FAQ Gaps, Link Gaps, Quality — all with auto-filters)
                      if `openpyxl` is installed, else CSV fallback.

HTML needs no third-party dependency (charts are hand-rolled SVG, no CDN).
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
        # utf-8-sig tolerates a BOM (some Windows tools add one).
        with open(path, "r", encoding="utf-8-sig") as fh:
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


def esc(x):
    return html.escape(str(x if x is not None else ""))


# ----------------------------- svg chart ------------------------------------
def svg_bar(title, pairs, unit=""):
    pairs = [(str(l), float(v or 0)) for l, v in pairs]
    if not pairs:
        return ""
    mx = max((v for _, v in pairs), default=0) or 1
    bar_h, gap, left, top, width = 22, 10, 170, 30, 540
    height = top + len(pairs) * (bar_h + gap) + 10
    rows = []
    for i, (label, val) in enumerate(pairs):
        y = top + i * (bar_h + gap)
        w = int((val / mx) * (width - left - 80))
        rows.append(
            f'<text x="0" y="{y + 15}" class="lbl">{esc(label[:26])}</text>'
            f'<rect x="{left}" y="{y}" width="{max(w,1)}" height="{bar_h}" rx="3" class="bar"/>'
            f'<text x="{left + max(w,1) + 6}" y="{y + 15}" class="val">{val:g}{unit}</text>'
        )
    return (f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">'
            f'<text x="0" y="16" class="ctitle">{esc(title)}</text>' + "".join(rows) + "</svg>")


# ----------------------------- html pieces ----------------------------------
def outline_html(page):
    rows = []
    for h in page.get("heading_outline", [])[:120]:
        lvl = int(h.get("level", 2) or 2)
        pad = (lvl - 1) * 18
        rows.append(f'<div class="ol" style="margin-left:{pad}px"><span class="lvl">H{lvl}</span> {esc(h.get("text"))}</div>')
    hc = page.get("heading_counts", {})
    cap = (f'<small>H1:{hc.get("h1",0)} · H2:{hc.get("h2",0)} · H3:{hc.get("h3",0)} · '
           f'H4+:{hc.get("h4_plus",0)} · words:{page.get("word_count_total",0)}</small>')
    return cap + "".join(rows) if rows else cap + "<small>(no headings captured)</small>"


def links_html(page):
    links = page.get("internal_links", []) or []
    cap = (f'<small><b>{page.get("internal_link_count", len(links))}</b> internal links · '
           f'<b>{page.get("unique_internal_targets","?")}</b> unique targets · '
           f'{page.get("external_link_count","?")} external</small>')
    if not links:
        return cap
    rows = ["<table><thead><tr><th>Anchor</th><th>Target</th><th>Section</th><th>Scope</th></tr></thead><tbody>"]
    for l in links[:50]:
        rows.append(f'<tr><td>{esc(l.get("anchor"))}</td>'
                    f'<td class="mono">{esc(l.get("href"))}</td>'
                    f'<td>{esc(l.get("section"))}</td><td>{esc(l.get("scope"))}</td></tr>')
    rows.append("</tbody></table>")
    if len(links) > 50:
        rows.append(f"<small>… {len(links) - 50} more (see report.xlsx → Internal Links)</small>")
    return cap + "".join(rows)


CSS = """
*{box-sizing:border-box} body{font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;
 color:#0f172a;max-width:1100px;margin:0 auto;padding:16px 28px;line-height:1.5}
h1{font-size:24px;border-bottom:3px solid #1e3a8a;padding-bottom:6px;color:#1e3a8a}
h2{font-size:18px;margin-top:28px;border-bottom:1px solid #cbd5e1;padding-bottom:4px;color:#1e3a8a}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.kpi{flex:1 1 140px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px}
.kpi .n{font-size:24px;font-weight:700;color:#1e3a8a} .kpi .l{font-size:12px;color:#475569}
.banner{padding:10px 14px;border-radius:8px;margin:8px 0;font-size:14px}
.ok{background:#dcfce7;border:1px solid #16a34a;color:#166534}
.warn{background:#fef3c7;border:1px solid #f59e0b;color:#92400e}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}
th,td{border:1px solid #cbd5e1;padding:4px 7px;text-align:left;vertical-align:top}
th{background:#eef2ff} .matrix td{text-align:center;font-weight:600}
.d0{background:#fee2e2;color:#991b1b}.d1{background:#fef3c7}.d2{background:#dbeafe}.d3{background:#dcfce7;color:#166534}
.p3{color:#b91c1c;font-weight:700}.p2{color:#b45309;font-weight:600}.p1{color:#1d4ed8}
.chart{width:100%;max-width:560px;margin:6px 0}
.chart .ctitle{font-size:13px;font-weight:700;fill:#1e3a8a}.chart .lbl{font-size:11px;fill:#334155}
.chart .val{font-size:11px;fill:#475569}.chart .bar{fill:#3b82f6}
.charts{display:flex;flex-wrap:wrap;gap:24px}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.controls input,.controls select{padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px}
.ol{font-size:13px;padding:1px 0}.lvl{display:inline-block;min-width:26px;font-size:10px;font-weight:700;color:#1e40af;font-family:monospace}
.mono{font-family:monospace;font-size:11px;word-break:break-all}
details{border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;margin:8px 0;background:#fbfdff}
summary{cursor:pointer;font-weight:600;color:#1e3a8a} small{color:#64748b} code{background:#f1f5f9;padding:1px 5px;border-radius:4px}
@media print{.controls{display:none} details{break-inside:avoid}}
"""
FILTER_JS = """
function f(){var q=(document.getElementById('q').value||'').toLowerCase();
var t=document.getElementById('ft').value,p=document.getElementById('fp').value;
document.querySelectorAll('#gaps tbody tr').forEach(function(r){
 var okq=r.innerText.toLowerCase().indexOf(q)>=0;
 var okt=!t||r.dataset.type===t; var okp=!p||r.dataset.prio===p;
 r.style.display=(okq&&okt&&okp)?'':'none';});}
"""


def build_html(run_dir, meta, clusters, gaps, pages, your, order):
    k = gaps.get("kpis", {})
    serp = gaps.get("serp", {})
    topic = esc(gaps.get("topic") or meta.get("topic") or "this page")
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           f"<title>Content-Gap Report — {topic}</title><style>{CSS}</style></head><body>"]
    out.append(f"<h1>Content-Gap Report — {topic}</h1>")
    out.append(f"<small>Your page: <code>{esc(gaps.get('your_url') or meta.get('your_url'))}</code> · "
               f"page type: <b>{esc(gaps.get('page_type') or meta.get('page_type'))}</b> · "
               f"pages compared: {len(order)}</small>")

    yr = serp.get("your_rank")
    if yr:
        out.append(f"<div class='banner ok'>✅ Your page ranks <b>#{esc(yr)}</b> for \"{esc(serp.get('query'))}\".</div>")
    else:
        out.append("<div class='banner warn'>⚠️ Your page did <b>not</b> appear in the top search results for this topic.</div>")

    cards = [("coverage_pct", "Topic coverage", "%"), ("missing_count", "Missing sections", ""),
             ("thin_count", "Thin sections", ""), ("faq_gap_count", "FAQ gaps", ""),
             ("link_gap_count", "Internal-link gaps", ""), ("quality_score", "Quality score", "")]
    out.append("<div class='kpis'>")
    for key, label, unit in cards:
        out.append(f"<div class='kpi'><div class='n'>{esc(k.get(key,0))}{unit}</div><div class='l'>{label}</div></div>")
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
    out.append(svg_bar("H2 headings", [(p.get("brand", "?"), (p.get("heading_counts", {}) or {}).get("h2", 0)) for p in pages]))
    out.append(svg_bar("FAQs answered", [(p.get("brand", "?"), len(p.get("faqs", []))) for p in pages]))
    out.append(svg_bar("Internal links", [(p.get("brand", "?"), p.get("internal_link_count", len(p.get("internal_links", [])))) for p in pages]))
    out.append("</div>")

    # page structure (H1/H2/H3 outline per page) — Content Writer v2 style
    out.append("<h2>Page structure — H1 / H2 / H3 outline per page</h2>")
    for p in pages:
        opn = " open" if p.get("is_ours") else ""
        out.append(f"<details{opn}><summary>{esc(p.get('brand'))}{' — OUR PAGE' if p.get('is_ours') else ''}</summary>{outline_html(p)}</details>")

    # internal linking (real links per page)
    out.append("<h2>Internal linking — real links per page</h2>")
    out.append("<small>Parsed directly from each page's HTML (anchor → target), so counts are exact.</small>")
    for p in pages:
        opn = " open" if p.get("is_ours") else ""
        out.append(f"<details{opn}><summary>{esc(p.get('brand'))} — {p.get('internal_link_count', len(p.get('internal_links', [])))} internal links</summary>{links_html(p)}</details>")

    # gaps table
    out.append("<h2>Prioritised gaps</h2>")
    out.append("<div class='controls'><input id='q' onkeyup='f()' placeholder='search gaps…'>"
               "<select id='ft' onchange='f()'><option value=''>all types</option>"
               "<option>missing</option><option>thin</option><option>unique</option><option>faq</option>"
               "<option>link</option><option>example</option><option>quality</option></select>"
               "<select id='fp' onchange='f()'><option value=''>all priorities</option>"
               "<option value='3'>P3</option><option value='2'>P2</option><option value='1'>P1</option></select></div>")
    out.append("<table id='gaps'><thead><tr><th>P</th><th>Type</th><th>Cluster</th><th>What to do</th><th>Exemplar</th></tr></thead><tbody>")
    for g in sorted(gaps.get("gaps", []), key=lambda x: -int(x.get("priority", 0) or 0)):
        pr = int(g.get("priority", 0) or 0)
        out.append(f"<tr data-type='{esc(g.get('type'))}' data-prio='{pr}'>"
                   f"<td class='p{pr}'>P{pr}</td><td>{esc(g.get('type'))}</td><td>{esc(g.get('cluster'))}</td>"
                   f"<td><b>{esc(g.get('title'))}</b><br><small>{esc(g.get('recommendation') or g.get('detail'))}</small></td>"
                   f"<td>{esc(g.get('exemplar_brand'))}</td></tr>")
    out.append("</tbody></table>")

    fg = gaps.get("faq_gaps", [])
    if fg:
        out.append("<h2>FAQ gaps (questions competitors answer, you don't)</h2><ul>")
        for q in fg:
            out.append(f"<li>{esc(q.get('question'))} <small>— answered by {esc(', '.join(q.get('answered_by', [])))}</small></li>")
        out.append("</ul>")
    lg = gaps.get("link_gaps", [])
    if lg:
        out.append("<h2>Internal-link gaps (targets competitors link, you don't)</h2><ul>")
        for l in lg:
            out.append(f"<li>{esc(l.get('topic_or_target'))} <small>— linked by {esc(', '.join(l.get('present_in', [])))}</small></li>")
        out.append("</ul>")

    q = (gaps.get("quality") or {}).get("per_brand", {})
    if q:
        out.append("<h2>Content-quality signals</h2><table><thead><tr><th>Page</th><th>Words</th><th>H2s</th>"
                   "<th>FAQs</th><th>Int. links</th><th>Schema</th><th>E-E-A-T</th><th>Freshness</th></tr></thead><tbody>")
        for b in order:
            r = q.get(b, {})
            out.append(f"<tr><td>{esc(b)}</td><td>{esc(r.get('word_count'))}</td><td>{esc(r.get('h2'))}</td>"
                       f"<td>{esc(r.get('faqs'))}</td><td>{esc(r.get('internal_links'))}</td>"
                       f"<td>{esc(', '.join(r.get('schema', []) or []))}</td>"
                       f"<td>{'yes' if r.get('eeat') else 'no'}</td><td>{esc(r.get('freshness'))}</td></tr>")
        out.append("</tbody></table>")

    out.append("<hr><small>Generated by the SEO Content-Gap Analyzer. Identifies gaps and briefs — "
               "it does not contain publishable copy. Internal links and headings are parsed from the "
               "live HTML; verify any figure before publishing.</small>")
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
        with open(os.path.join(run_dir, "internal_links.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["brand", "anchor", "target", "section", "scope"])
            for p in pages:
                for l in p.get("internal_links", []):
                    w.writerow([p.get("brand"), l.get("anchor"), l.get("href"), l.get("section"), l.get("scope")])
        with open(os.path.join(run_dir, "gaps.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["priority", "type", "cluster", "title", "recommendation", "exemplar"])
            for g in gaps.get("gaps", []):
                w.writerow([g.get("priority"), g.get("type"), g.get("cluster"), g.get("title"),
                            g.get("recommendation") or g.get("detail"), g.get("exemplar_brand")])
        return None, "openpyxl not installed — wrote gaps.csv + internal_links.csv (pip install openpyxl for the XLSX)."

    wb = Workbook()
    head, fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1E3A8A")

    def hdr(ws, cols):
        ws.append(cols)
        for c in ws[1]:
            c.font = head; c.fill = fill

    # Overview
    ws = wb.active; ws.title = "Overview"
    k = gaps.get("kpis", {})
    hdr(ws, ["KPI", "Value"])
    for label, key in [("Topic coverage %", "coverage_pct"), ("Missing sections", "missing_count"),
                       ("Thin sections", "thin_count"), ("Unique sections", "unique_count"),
                       ("FAQ gaps", "faq_gap_count"), ("Internal-link gaps", "link_gap_count"),
                       ("Example gaps", "example_gap_count"), ("Quality score", "quality_score"),
                       ("Your word count", "your_word_count"), ("Competitor median words", "competitor_median_word_count")]:
        ws.append([label, k.get(key, 0)])
    ws.append([]); ws.append(["Page", "Words", "H2s", "Internal links"])
    start = ws.max_row
    for p in pages:
        ws.append([p.get("brand", "?"), p.get("word_count_total", 0),
                   (p.get("heading_counts", {}) or {}).get("h2", 0),
                   p.get("internal_link_count", len(p.get("internal_links", [])))])
    chart = BarChart(); chart.title = "Word count by page"; chart.type = "bar"
    chart.add_data(Reference(ws, min_col=2, min_row=start, max_row=ws.max_row), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=start + 1, max_row=ws.max_row))
    ws.add_chart(chart, "F2")

    # Cluster matrix
    ws = wb.create_sheet("Cluster Matrix")
    hdr(ws, ["Cluster"] + order)
    for c in clusters.get("clusters", []):
        ws.append([c.get("name")] + [int((c.get("brands") or {}).get(b, {}).get("depth", 0) or 0) for b in order])
    ws.auto_filter.ref = ws.dimensions

    # Page Structure (H1/H2/H3 outline per page) — CW v2 style
    ws = wb.create_sheet("Page Structure")
    hdr(ws, ["Page", "Level", "Heading"])
    for p in pages:
        for h in p.get("heading_outline", []):
            ws.append([p.get("brand"), "H" + str(h.get("level", "")), h.get("text")])
    ws.auto_filter.ref = ws.dimensions

    # Internal Links (the real, parsed links)
    ws = wb.create_sheet("Internal Links")
    hdr(ws, ["Page", "Anchor", "Target", "Section", "Scope"])
    for p in pages:
        for l in p.get("internal_links", []):
            ws.append([p.get("brand"), l.get("anchor"), l.get("href"), l.get("section"), l.get("scope")])
    ws.auto_filter.ref = ws.dimensions

    # Gaps
    ws = wb.create_sheet("Gaps")
    hdr(ws, ["Priority", "Type", "Cluster", "Title", "Recommendation", "Exemplar"])
    pr_fill = {3: PatternFill("solid", fgColor="FECACA"), 2: PatternFill("solid", fgColor="FEF3C7"),
               1: PatternFill("solid", fgColor="DBEAFE")}
    for g in sorted(gaps.get("gaps", []), key=lambda x: -int(x.get("priority", 0) or 0)):
        ws.append([g.get("priority"), g.get("type"), g.get("cluster"), g.get("title"),
                   g.get("recommendation") or g.get("detail"), g.get("exemplar_brand")])
        f = pr_fill.get(int(g.get("priority", 0) or 0))
        if f:
            ws.cell(row=ws.max_row, column=1).fill = f
    ws.auto_filter.ref = ws.dimensions

    # FAQ gaps / Link gaps / Quality
    ws = wb.create_sheet("FAQ Gaps"); hdr(ws, ["Question", "Answered by"])
    for q in gaps.get("faq_gaps", []):
        ws.append([q.get("question"), ", ".join(q.get("answered_by", []))])
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Link Gaps"); hdr(ws, ["Topic / target", "Linked by"])
    for l in gaps.get("link_gaps", []):
        ws.append([l.get("topic_or_target"), ", ".join(l.get("present_in", []))])
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Quality")
    hdr(ws, ["Page", "Words", "H2s", "FAQs", "Internal links", "Schema", "E-E-A-T", "Freshness"])
    q = (gaps.get("quality") or {}).get("per_brand", {})
    for b in order:
        r = q.get(b, {})
        ws.append([b, r.get("word_count"), r.get("h2"), r.get("faqs"), r.get("internal_links"),
                   ", ".join(r.get("schema", []) or []), "yes" if r.get("eeat") else "no", r.get("freshness")])
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
    print("HTML  ->", build_html(run_dir, meta, clusters, gaps, pages, your, order))
    xlsx_path, note = build_xlsx(run_dir, meta, clusters, gaps, pages, your, order)
    if xlsx_path:
        print("XLSX  ->", xlsx_path)
    if note:
        print("NOTE :", note)
    print("Open report.html in a browser and Print -> Save as PDF for a shareable PDF.")


if __name__ == "__main__":
    main()
