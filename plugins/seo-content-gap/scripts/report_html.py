"""HTML renderer for the content-gap report (screen + print/PDF variants).

render(ctx, print_mode=False) -> str. `ctx` comes from report_core.build_context.
Self-contained output: inline CSS/JS, no CDN. Print mode expands every
collapsible block and leaves out raw link/image/page-structure dumps (they stay
in the HTML and XLSX) so the PDF reads as a document.
"""
from datetime import date

from report_core import (DEPTH_LABEL, FIELD_CATEGORY, PRIORITY_LABEL, esc, keyword_checks, internal_link_count,
                         median, onpage_internal_links, rate, serp_matrix, sim_verdict, similarity)

STATUS = {"good": "Good", "ni": "Needs improvement", "poor": "Poor", "": "No data"}

CSS = r"""
:root{--ink:#0f172a;--text:#334155;--muted:#64748b;--line:#e2e8f0;--line2:#cbd5e1;
--bg:#ffffff;--panel:#f8fafc;--accent:#1e3a5f;--you:#f1f5f9;
--good:#15803d;--ni:#b45309;--poor:#b91c1c}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 "Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;font-variant-numeric:tabular-nums}
a{color:var(--accent)}
.wrap{display:grid;grid-template-columns:232px minmax(0,1fr);max-width:1320px;margin:0 auto}
nav.toc{position:sticky;top:0;align-self:start;height:100vh;padding:28px 20px 28px 24px;border-right:1px solid var(--line);font-size:13px}
nav.toc .brand{font-weight:600;color:var(--ink);font-size:13px;letter-spacing:.02em;margin-bottom:18px}
nav.toc ol{list-style:none;margin:0;padding:0;counter-reset:s}
nav.toc li{counter-increment:s;margin:0}
nav.toc a{display:block;padding:6px 8px;border-radius:4px;color:var(--text);text-decoration:none}
nav.toc a::before{content:counter(s) ".";color:var(--muted);display:inline-block;width:20px}
nav.toc a:hover{background:var(--panel);color:var(--ink)}
nav.toc .dl{margin-top:24px;padding-top:16px;border-top:1px solid var(--line)}
nav.toc .dl a::before{content:none}
main{padding:36px 48px 64px;min-width:0}
header.cover{border-bottom:2px solid var(--accent);padding-bottom:20px;margin-bottom:8px}
.eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font-size:26px;line-height:1.25;color:var(--ink);margin:6px 0 10px;font-weight:600}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px 24px;font-size:12.5px;margin-top:14px}
.meta div span{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.meta div b{font-weight:500;color:var(--ink);overflow-wrap:anywhere}
section{padding-top:36px}
h2{font-size:18px;color:var(--ink);margin:0 0 4px;font-weight:600;display:flex;gap:10px;align-items:baseline}
h2 .n{color:var(--muted);font-weight:500;font-size:14px;min-width:22px}
.lede{color:var(--muted);margin:0 0 18px;max-width:78ch}
h3{font-size:14px;color:var(--ink);margin:26px 0 10px;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border:1px solid var(--line);border-radius:6px;margin-bottom:22px}
.kpi{padding:16px 18px;border-right:1px solid var(--line)}
.kpi:last-child{border-right:0}
.kpi .l{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.kpi .v{font-size:26px;color:var(--ink);font-weight:600;margin:4px 0 2px}
.kpi .v small{font-size:13px;color:var(--muted);font-weight:500}
.kpi .s{font-size:12.5px}
.findings{margin:0;padding:0;list-style:none;border-top:1px solid var(--line)}
.findings li{display:grid;grid-template-columns:150px 1fr;gap:16px;padding:12px 0;border-bottom:1px solid var(--line)}
.findings li b{color:var(--ink);font-weight:600}
.tbl{width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{background:var(--panel);color:var(--ink);font-weight:600;font-size:12px;border-bottom:1px solid var(--line2);white-space:nowrap}
thead th em{display:block;font-style:normal;font-weight:500;color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em}
tbody tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;white-space:nowrap}
th.you,td.you,tr.you td{background:var(--you)}
tr.you td:first-child{box-shadow:inset 3px 0 0 var(--accent);font-weight:600;color:var(--ink)}
td.rowh{color:var(--ink);font-weight:500;white-space:nowrap}
td.rowh small{display:block;color:var(--muted);font-weight:400;font-size:11.5px}
.m{display:inline-block}
.m{color:var(--ink)}
.m-poor::before,.m-ni::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;vertical-align:middle;position:relative;top:-1px}
.m-poor::before{background:var(--poor)}.m-ni::before{background:var(--ni)}
.m-poor{font-weight:600}
.st{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.st i{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.st-good i{background:var(--good)}.st-ni i{background:var(--ni)}.st-poor i{background:var(--poor)}
.pill{display:inline-block;font-size:11px;font-weight:600;padding:1px 8px;border-radius:10px;border:1px solid var(--line2);color:var(--text);white-space:nowrap}
.pill.high{border-color:var(--ink);color:var(--ink)}
.legend{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:12px;color:var(--muted);margin:10px 0 0}
.printonly{display:none}
.note{font-size:12px;color:var(--muted);margin-top:8px}
.sample{border:1px dashed var(--line2);background:var(--panel);padding:8px 12px;border-radius:4px;font-size:12px;color:var(--text);margin-bottom:12px}
.seg{display:inline-flex;border:1px solid var(--line2);border-radius:5px;overflow:hidden;margin-bottom:12px}
.seg button{font:inherit;font-size:12.5px;border:0;background:#fff;color:var(--text);padding:5px 14px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--accent);color:#fff}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px}
.bar{display:grid;grid-template-columns:130px 1fr 54px;gap:10px;align-items:center;font-size:12.5px;padding:3px 0}
.bar .t{height:8px;background:var(--line);border-radius:2px;overflow:hidden}
.bar .t b{display:block;height:100%;background:#94a3b8}
.bar.you .t b{background:var(--accent)}
.bar.you span:first-child{font-weight:600;color:var(--ink)}
.bar span:last-child{text-align:right;color:var(--ink)}
footer{margin-top:48px;padding-top:14px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}
@media (max-width:960px){.wrap{grid-template-columns:1fr}nav.toc{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}
 main{padding:24px 16px}.meta,.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi:nth-child(2){border-right:0}
 .two{grid-template-columns:1fr}.findings li{grid-template-columns:1fr;gap:2px}}
@media print{
 @page{size:A4;margin:14mm 12mm 16mm}
 body{font-size:10.5px}
 .wrap{display:block;max-width:none}
 nav.toc,.seg,.noprint{display:none!important}
 main{padding:0}
 section{padding-top:18px;break-inside:auto}
 section.pb{break-before:page}
 h2,h3{break-after:avoid}
 tr,.kpi,.findings li{break-inside:avoid}
 .tbl{overflow:visible;border-color:#cbd5e1}
 th,td{padding:5px 7px}
 thead{display:table-header-group}
 .both [data-view]{display:block!important}
 .printonly{display:block}
 .kpi .v{font-size:20px}
 a{color:inherit;text-decoration:none}
}

.mx th.c,.mx td.c{text-align:center;white-space:nowrap}
.yes{color:var(--ink);font-weight:600}.no{color:#cbd5e1}
.tag{display:inline-block;min-width:26px;margin-right:8px;padding:0 5px;border:1px solid var(--line2);border-radius:3px;font-size:10.5px;font-weight:600;color:var(--muted);text-align:center;line-height:16px;vertical-align:1px}
.dp{display:block;color:var(--muted);font-size:10.5px}
.muted{color:var(--muted)}.nowrap{white-space:nowrap}
.tree td.h{white-space:normal;min-width:320px}
.tree tr.lv1 td.h{font-weight:600;color:var(--ink)}
.tree tr.lv2 td.h{padding-left:28px;color:var(--ink)}
.tree tr.lv3 td.h{padding-left:52px}
.tree tr.lv4 td.h{padding-left:76px;color:var(--muted)}
.scroll{max-height:640px;overflow:auto}
.scroll thead th{position:sticky;top:0;z-index:1}
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 10px}
.tools .seg{margin:0}
.search{font:inherit;font-size:12.5px;padding:5px 10px;border:1px solid var(--line2);border-radius:5px;min-width:220px}
.btn{font:inherit;font-size:12.5px;padding:5px 12px;border:1px solid var(--line2);border-radius:5px;background:#fff;color:var(--text);cursor:pointer}
.callout{border-left:3px solid var(--accent);background:var(--panel);padding:10px 14px;margin:16px 0;font-size:13px}
details.acc{border:1px solid var(--line);border-radius:6px;margin:8px 0;background:#fff}
details.acc>summary{cursor:pointer;padding:10px 14px;display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;list-style:none}
details.acc>summary::-webkit-details-marker{display:none}
details.acc>summary::before{content:"▸";color:var(--muted);width:10px}
details.acc[open]>summary::before{content:"▾"}
details.acc>summary b{color:var(--ink);font-weight:600}
details.acc>summary .muted{font-size:12px}
ol.outline{list-style:none;margin:0;padding:4px 14px 12px;font-size:13px}
ol.outline li{padding:3px 0;border-bottom:1px solid #f1f5f9}
ol.outline li.lv2{padding-left:22px}ol.outline li.lv3{padding-left:44px}ol.outline li.lv4{padding-left:66px;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:4px 14px 14px}
.card{border:1px solid var(--line);border-radius:6px;padding:12px 14px;min-width:0}
.card.yours{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.card.absent{background:var(--panel)}
.card .ch{display:flex;justify-content:space-between;gap:10px;font-size:12px;margin-bottom:6px}
.card .ch b{font-size:13px;color:var(--ink)}
.card .hd{font-weight:600;color:var(--ink);margin-bottom:6px}
.card .sum{font-size:12.5px;margin:0 0 8px;color:var(--text)}
.card .sum span{display:inline-block;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-right:6px}
.card .text{font-size:12.5px;line-height:1.6;max-height:220px;overflow:auto;border-top:1px solid var(--line);padding-top:8px;white-space:pre-line}
.card .sim{display:block;margin-top:8px;font-size:11.5px;color:var(--muted)}
ol.faq{margin:0;padding:6px 18px 12px 40px}
ol.faq li{padding:8px 0;border-bottom:1px solid #f1f5f9}
ol.faq .q{margin:0 0 4px;font-weight:600;color:var(--ink)}
ol.faq .a{margin:0;font-size:13px}
@media (max-width:960px){.cards{grid-template-columns:1fr}.tree td.h{min-width:220px}}
@media print{
 .scroll{max-height:none;overflow:visible}
 .card .text{max-height:none;overflow:visible}
 .cards{grid-template-columns:1fr 1fr}
 .card,details.acc li{break-inside:avoid}
 details.acc{border:0;border-top:1px solid var(--line);border-radius:0}
 details.acc>summary::before{content:none}
 .tree td.h{min-width:0}
}

main{counter-reset:sec}
section{counter-increment:sec}
h2 .n::before{content:counter(sec)}
nav.toc{overflow:auto}
.na{border:1px dashed var(--line2);border-radius:6px;padding:14px 16px;background:var(--panel);margin:0 0 14px}
.na-h{font-weight:600;color:var(--ink);margin-bottom:4px}
.na p{margin:4px 0}
.gap{border:1px solid var(--line);border-radius:6px;margin:8px 0}
.gap>summary{display:grid;grid-template-columns:80px 90px 1fr auto;gap:12px;align-items:baseline;padding:10px 14px;cursor:pointer;list-style:none}
.gap>summary::-webkit-details-marker{display:none}
.gap .body{padding:0 14px 12px 196px;font-size:13px}
.gap .body p{margin:6px 0}
.gap .body b{color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line2);border-radius:10px;padding:1px 9px;font-size:12px;white-space:nowrap}
.struct{margin:0;padding:4px 14px 12px;list-style:none}
.struct li{padding:8px 0;border-bottom:1px solid #f1f5f9}
.struct li.lv2{padding-left:20px}.struct li.lv3{padding-left:40px}.struct li.lv4{padding-left:60px}
.struct .t{font-weight:600;color:var(--ink)}
.struct .x{font-size:12.5px;margin:4px 0 0;white-space:pre-line}
.linktbl td{font-size:12px;overflow-wrap:anywhere}
@media (max-width:960px){.gap>summary{grid-template-columns:70px 1fr}.gap>summary .sb{display:none}.gap .body{padding-left:14px}}
@media print{.gap{border:0;border-top:1px solid var(--line);border-radius:0}.gap .body{padding-left:14px}}

.kpis.k3{gap:1px;background:var(--line);grid-template-columns:repeat(3,minmax(0,1fr))}
.kpis.k3 .kpi{background:var(--bg);border:0}
.tbl.inner{margin:0 14px 12px;width:auto}
@media (max-width:960px){.kpis.k3{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

JS = r"""
function flt(b,id){[...b.parentNode.children].forEach(x=>x.setAttribute("aria-pressed",x===b));var t=document.getElementById(id);t.dataset.f=b.dataset.f;apply(t)}
function srch(i,id){var t=document.getElementById(id);t.dataset.q=i.value.toLowerCase();apply(t)}
function apply(t){var f=t.dataset.f||"all",q=t.dataset.q||"";t.querySelectorAll("tbody tr").forEach(r=>{var ok=(f=="all")||(f=="miss"&&r.dataset.you=="0"&&+r.dataset.n>=1)||(f=="shared"&&+r.dataset.n>=2);if(q&&!r.textContent.toLowerCase().includes(q))ok=false;r.hidden=!ok})}
function accAll(sel,open){document.querySelectorAll(sel+" details").forEach(d=>d.open=open)}
function dev(b,k){[...b.parentNode.children].forEach(x=>x.setAttribute("aria-pressed",x===b));document.querySelectorAll("[data-view]").forEach(e=>e.hidden=e.dataset.view!==k)}
"""


# ----------------------------------------------------------------- formatting
def fms(v):
    if v is None:
        return "—"
    return f"{v / 1000:.1f} s" if v >= 1000 else f"{int(v)} ms"


def fcls(v):
    return "—" if v is None else f"{v:.2f}"


def fnum(v):
    return "—" if v is None else f"{v:,}"


def mark(value_text, status):
    return f'<span class="m{" m-" + status if status in ("ni", "poor") else ""}">{value_text}</span>'


def dot(status):
    return f'<span class="st st-{status or "na"}"><i></i>{STATUS.get(status, "")}</span>'


class H:
    """Small builder that keeps per-report state (brand order, your brand)."""

    def __init__(self, ctx, print_mode):
        self.c, self.p = ctx, print_mode
        self.order, self.your = ctx["order"], ctx["your"]
        self.o = []

    def A(self, s):
        self.o.append(s)

    def you(self, b):
        return " you" if b == self.your else ""

    def trc(self, b):
        return f' class="you"' if b == self.your else ""

    def th_brands(self, cls="c"):
        return "".join(f'<th class="{cls}{self.you(b)}">{esc(b)}{"<em>Your page</em>" if b == self.your else ""}</th>' for b in self.order)

    def yes(self, v, b):
        return f'<td class="c{self.you(b)}">{"<span class=yes>✓</span>" if v else "<span class=no>—</span>"}</td>'

    def section(self, id_, title, lede="", pb=True):
        self.A(f'<section id="{id_}"{" class=pb" if pb else ""}><h2><span class="n"></span>{title}</h2>'
               + (f'<p class="lede">{lede}</p>' if lede else ""))

    def unavailable(self, what, will_show):
        self.A(f'<div class="na"><div class="na-h">Not available yet</div><p>{what}</p>'
               f'<p class="muted">When connected, this section shows: {will_show}</p></div>')

    def filterbar(self, target, opts):
        btns = "".join(f'<button aria-pressed="{"true" if i == 0 else "false"}" data-f="{k}" onclick="flt(this,\'{target}\')">{esc(l)}</button>'
                       for i, (k, l) in enumerate(opts))
        self.A(f'<div class="tools noprint"><div class="seg" role="group">{btns}</div>'
               f'<input class="search" type="search" placeholder="Search…" aria-label="Search" oninput="srch(this,\'{target}\')"></div>')

    def details(self, summary_html, body_html):
        self.A(f'<details class="acc"{" open" if self.p else ""}><summary>{summary_html}</summary>{body_html}</details>')


# ====================================================================== render
def render(ctx, print_mode=False):
    h = H(ctx, print_mode)
    A = h.A
    c = ctx
    order, your, pages, topic = c["order"], c["your"], c["pages"], c["topic"]
    kpi, qual = c["kpis"], c["quality"]
    today = date.today().strftime("%d %b %Y")

    A('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      f'<title>SEO Competitive Audit</title><style>{CSS}</style></head><body><div class="wrap">')
    toc = [("summary", "Executive summary"), ("speed", "Page speed &amp; Core Web Vitals"), ("tech", "Technical &amp; on-page SEO"),
           ("keywords", "Keywords"), ("visibility", "Search visibility &amp; authority"), ("headings", "Heading structure"),
           ("topics", "Topic coverage &amp; gaps"), ("content", "Content by topic"), ("faqs", "FAQs"),
           ("links", "Links &amp; images"), ("actions", "Recommendations"), ("method", "Method &amp; data sources")]
    A('<nav class="toc" aria-label="Contents"><div class="brand">SEO Competitive Audit</div><ol>'
      + "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in toc)
      + '</ol><div class="dl"><a href="report.xlsx">Download XLSX</a><a href="report.pdf">Download PDF</a></div></nav><main>')
    A(f'<header class="cover"><div class="eyebrow">SEO Competitive Audit · {esc((c["meta"].get("page_type") or "").title())} page</div>'
      f'<h1>{esc(topic[:1].upper() + topic[1:])}: {esc(your)} vs {len(order) - 1} competitors</h1><div class="meta">'
      f'<div><span>Page audited</span><b>{esc((pages[your].get("url") or "").replace("https://", ""))}</b></div>'
      f'<div><span>Market</span><b>{esc(c["meta"].get("market") or "India")} · Google</b></div>'
      f'<div><span>Competitors</span><b>{esc(", ".join(order[1:]))}</b></div>'
      f'<div><span>Report date</span><b>{today}</b></div></div></header>')

    summary(h, today)
    speed(h)
    technical(h)
    keywords(h)
    visibility(h)
    headings(h)
    topics(h)
    content(h)
    faqs(h)
    links(h)
    actions(h)
    method(h)
    A(f'<footer>SEO Content-Gap Analyzer · run: {esc(c["run_name"])} · generated {today}</footer></main></div><script>{JS}</script></body></html>')
    return "".join(h.o)


# -------------------------------------------------------------------- sections
def _psi(h, b, device):
    r = (h.c["psi_by"].get(b) or {}).get(device) or {}
    return r if r and not r.get("error") else None


def summary(h, today):
    c, A = h.c, h.A
    your, order, kpi, qual = c["your"], c["order"], c["kpis"], c["quality"]
    ra = (c["gaps"].get("ranking_assessment") or {}).get(your) or {}
    h.section("summary", "Executive summary", esc(ra.get("google") or ""), pb=False)
    tiles = []
    tiles.append(("Content coverage", f'{kpi.get("coverage_pct", "—")}%', f'{kpi.get("missing_count", 0)} topics missing · {kpi.get("thin_count", 0)} thin'))
    if qual:
        ranked = sorted(qual, key=lambda b: -((qual[b] or {}).get("quality_score") or 0))
        pos = next((i + 1 for i, b in enumerate(ranked) if b.lower() == your.lower()), None)
        tiles.append(("Content quality", f'{(qual.get(your) or {}).get("quality_score", "—")}<small> / 100</small>', f"Rank {pos} of {len(ranked)} pages" if pos else ""))
    m = _psi(h, your, "mobile")
    if m:
        f = m.get("field") or {}
        cat = FIELD_CATEGORY.get(f.get("overall_category") or "", "")
        scope = "site-wide" if f.get("origin_fallback") else "this page"
        tiles.append(("Core Web Vitals (mobile)", STATUS[cat] if cat else "No data",
                      (f'Real users, {scope}: LCP {fms(f.get("lcp_ms"))} · INP {fms(f.get("inp_ms"))} · CLS {fcls(f.get("cls"))}') if cat
                      else "Not enough Chrome traffic for real-user data"))
        scores = sorted(((_psi(h, b, "mobile") or {}).get("scores", {}).get("performance") for b in order), key=lambda x: -(x or -1))
        mine = m["scores"].get("performance")
        tiles.append(("Mobile performance", f'{mine}<small> / 100</small>', f"Lab test · rank {scores.index(mine) + 1} of {len(order)}" if mine is not None else ""))
    else:
        tiles.append(("Page speed", "Not available", "PageSpeed Insights not run"))
    a = c["auth_by"].get(your)
    if a:
        comp_rd = median([(c["auth_by"].get(b) or {}).get("refdomains") for b in order[1:]])
        tiles.append(("Authority (Ahrefs)", f'UR {a.get("url_rating", "—")}',
                      f'{fnum(a.get("refdomains"))} referring domains · competitor median {fnum(round(comp_rd)) if comp_rd is not None else "—"}'))
        tiles.append(("Organic keywords (Ahrefs)", fnum(a.get("org_keywords")), f'{fnum(a.get("org_keywords_top3"))} in top 3 · ~{fnum(a.get("org_traffic"))} visits / month'))
    else:
        tiles.append(("Authority", "Not available", "Ahrefs not connected"))
    rk = (c["ranking"].get("our_ranking") or {})
    if len(tiles) < 6:
        tiles.append(("Google ranking (web search)", f'#{rk.get("best_position")}' if rk.get("found") else "Not ranked",
                      f'Across {len(c["ranking"].get("queries_used") or [])} target queries checked'))
    A('<div class="kpis k3">' + "".join(f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for l, v, s in tiles) + '</div>')
    A('<h3>Highest-priority gaps</h3><ul class="findings">')
    for g in [g for g in c["gap_list"] if int(g.get("priority") or 0) == 3][:6]:
        A(f'<li><b>{esc((g.get("type") or "").title())}</b><span>{esc(g.get("title"))}</span></li>')
    A('</ul></section>')


def speed(h):
    c, A = h.c, h.A
    order, your, psi = c["order"], c["your"], c["psi"]
    h.section("speed", "Page speed &amp; Core Web Vitals")
    if not psi:
        h.unavailable("Google PageSpeed Insights was not run for this report.",
                      "Core Web Vitals from real Chrome users (LCP, INP, CLS) and Lighthouse lab metrics for mobile and desktop, "
                      "Lighthouse accessibility / best-practice / SEO scores, and the top fixes for your page.")
        A('</section>')
        return
    A(f'<p class="lede">Google PageSpeed Insights, measured {esc((psi.get("fetched_at") or "")[:10])}. '
      '<b>Real users</b> are Chrome UX Report 75th-percentile values over the last 28 days — the numbers Google uses for ranking. '
      '<b>Lab</b> is a single Lighthouse test on a throttled device, useful for diagnosing causes. Values outside Google’s thresholds are marked.</p>')
    A('<div class="seg noprint" role="group" aria-label="Device"><button aria-pressed="true" onclick="dev(this,\'mobile\')">Mobile</button>'
      '<button aria-pressed="false" onclick="dev(this,\'desktop\')">Desktop</button></div><div class="both">')
    for device in ("mobile", "desktop"):
        A(f'<div data-view="{device}"{" hidden" if device == "desktop" else ""}><h3 class="printonly">{device.title()}</h3>')
        A('<h3>Real-user Core Web Vitals</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Assessment</th>'
          '<th class="num">LCP<em>≤ 2.5 s</em></th><th class="num">INP<em>≤ 200 ms</em></th><th class="num">CLS<em>≤ 0.10</em></th>'
          '<th class="num">FCP<em>≤ 1.8 s</em></th><th class="num">TTFB<em>≤ 0.8 s</em></th><th>Data scope</th></tr></thead><tbody>')
        for b in order:
            r = (c["psi_by"].get(b) or {}).get(device) or {}
            if r.get("error") or not r:
                A(f'<tr{h.trc(b)}><td>{esc(b)}</td><td colspan="7" class="muted">Not measured: {esc((r.get("error") or "no result")[:120])}</td></tr>')
                continue
            f = r.get("field") or {}
            if not f.get("has_data"):
                A(f'<tr{h.trc(b)}><td>{esc(b)}</td><td colspan="7" class="muted">Not enough Chrome traffic for real-user data — see lab results</td></tr>')
                continue
            cat = FIELD_CATEGORY.get(f.get("overall_category") or "", "")
            A(f'<tr{h.trc(b)}><td>{esc(b)}</td><td>{dot(cat)}</td>'
              f'<td class="num">{mark(fms(f.get("lcp_ms")), rate("lcp_ms", f.get("lcp_ms")))}</td>'
              f'<td class="num">{mark(fms(f.get("inp_ms")), rate("inp_ms", f.get("inp_ms")))}</td>'
              f'<td class="num">{mark(fcls(f.get("cls")), rate("cls", f.get("cls")))}</td>'
              f'<td class="num">{mark(fms(f.get("fcp_ms")), rate("fcp_ms", f.get("fcp_ms")))}</td>'
              f'<td class="num">{mark(fms(f.get("ttfb_ms")), rate("ttfb_ms", f.get("ttfb_ms")))}</td>'
              f'<td>{"Site-wide (page has too little traffic)" if f.get("origin_fallback") else "This page"}</td></tr>')
        A('</tbody></table></div>')
        A('<h3>Lab test (Lighthouse)</h3><div class="tbl"><table><thead><tr><th>Page</th><th class="num">Performance</th>'
          '<th class="num">LCP<em>≤ 2.5 s</em></th><th class="num">CLS<em>≤ 0.10</em></th><th class="num">TBT<em>≤ 200 ms</em></th>'
          '<th class="num">FCP<em>≤ 1.8 s</em></th><th class="num">Speed Index<em>≤ 3.4 s</em></th><th class="num">Page weight</th>'
          '<th class="num">Accessibility</th><th class="num">Best practices</th><th class="num">SEO</th></tr></thead><tbody>')
        for b in order:
            r = _psi(h, b, device)
            if not r:
                A(f'<tr{h.trc(b)}><td>{esc(b)}</td><td colspan="10" class="muted">Not measured</td></tr>')
                continue
            lab, sc = r.get("lab") or {}, r.get("scores") or {}
            A(f'<tr{h.trc(b)}><td>{esc(b)}</td><td class="num">{mark(sc.get("performance", "—"), rate("score", sc.get("performance")))}</td>'
              f'<td class="num">{mark(fms(lab.get("lcp_ms")), rate("lcp_ms", lab.get("lcp_ms")))}</td>'
              f'<td class="num">{mark(fcls(lab.get("cls")), rate("cls", lab.get("cls")))}</td>'
              f'<td class="num">{mark(fms(lab.get("tbt_ms")), rate("tbt_ms", lab.get("tbt_ms")))}</td>'
              f'<td class="num">{mark(fms(lab.get("fcp_ms")), rate("fcp_ms", lab.get("fcp_ms")))}</td>'
              f'<td class="num">{mark(fms(lab.get("si_ms")), rate("si_ms", lab.get("si_ms")))}</td>'
              f'<td class="num">{(lab.get("bytes") or 0) / 1048576:.1f} MB</td>'
              + "".join(f'<td class="num">{mark(sc.get(k, "—"), rate("score", sc.get(k)))}</td>' for k in ("accessibility", "best-practices", "seo"))
              + '</tr>')
        A('</tbody></table></div>')
        r = _psi(h, your, device)
        if r and r.get("fixes"):
            A(f'<h3>Top fixes for your page ({device})</h3><div class="tbl"><table><thead><tr><th>Lighthouse finding</th>'
              '<th>Metrics affected</th><th class="num">Est. saving</th><th>Detail</th></tr></thead><tbody>')
            for fx in r["fixes"][:8]:
                A(f'<tr><td>{esc(fx.get("title"))}</td><td>{esc(", ".join(fx.get("metrics") or []))}</td>'
                  f'<td class="num">{fms(fx.get("savings_ms")) if fx.get("savings_ms") else "—"}</td><td>{esc(fx.get("display") or "")}</td></tr>')
            A('</tbody></table></div>')
        A('</div>')
    A('</div><div class="legend"><span>' + dot("good") + '</span><span>' + dot("ni") + '</span><span>' + dot("poor") + '</span>'
      '<span>INP exists only in real-user data; Lighthouse lab tests cannot measure it.</span></div></section>')


def technical(h):
    c, A = h.c, h.A
    order, pages, qual = c["order"], c["pages"], c["quality"]
    h.section("tech", "Technical &amp; on-page SEO", "Checks from the raw HTML of each page. Values outside recommended ranges are marked.")
    A('<div class="tbl"><table class="mx"><thead><tr><th>Check</th>' + h.th_brands("num") + '</tr></thead><tbody>')

    def row(label, hint, fn, rule=lambda v: ""):
        cells = []
        for b in order:
            v = fn(b)
            cells.append(f'<td class="num{h.you(b)}">{mark(esc(v) if v is not None else "—", rule(v) if v is not None else "")}</td>')
        A(f'<tr><td class="rowh">{label}{f"<small>{hint}</small>" if hint else ""}</td>{"".join(cells)}</tr>')

    P = lambda b: pages[b]
    row("Title length", "50–60 chars", lambda b: len(P(b).get("title") or ""), lambda v: "ni" if v > 60 or v < 30 else "")
    row("Meta description", "120–160 chars", lambda b: len(P(b).get("meta_description") or ""), lambda v: "ni" if v > 160 or v < 70 else "")
    row("H1 count", "exactly 1", lambda b: c["hcounts"][b][1], lambda v: "poor" if v != 1 else "")
    row("H2 / H3 / H4", "", lambda b: "{} / {} / {}".format(*[c["hcounts"][b][l] for l in (2, 3, 4)]))
    row("Visible words", "", lambda b: f'{int(P(b).get("word_count_total") or 0):,}')
    row("Tables", "", lambda b: P(b).get("tables_count"))
    row("Images", "", lambda b: P(b).get("image_count"))
    row("Images missing alt", "", lambda b: max(0, int(P(b).get("image_count") or 0) - int(P(b).get("image_alt_count") or 0)), lambda v: "ni" if v > 0 else "")
    row("Structured-data types", "JSON-LD", lambda b: len(P(b).get("schema_types") or []))
    row("FAQPage schema", "", lambda b: "Yes" if "FAQPage" in (P(b).get("schema_types") or []) else "No", lambda v: "ni" if v == "No" else "")
    row("Named author", "E-E-A-T", lambda b: "Yes" if P(b).get("author") else "No", lambda v: "ni" if v == "No" else "")
    row("Named reviewer", "E-E-A-T", lambda b: "Yes" if P(b).get("reviewer") else "No")
    row("Last updated date", "", lambda b: P(b).get("modified_date") or P(b).get("published_date") or "Not shown", lambda v: "ni" if v == "Not shown" else "")
    row("Internal links", "in article body", lambda b: internal_link_count(P(b), qual))
    row("External links", "", lambda b: P(b).get("external_link_count"))
    if c["psi_by"]:
        row("Lighthouse SEO score", "mobile", lambda b: ((_psi(h, b, "mobile") or {}).get("scores") or {}).get("seo"), lambda v: rate("score", v))
        row("Server response (lab)", "≤ 0.8 s", lambda b: fms(((_psi(h, b, "mobile") or {}).get("lab") or {}).get("ttfb_ms")))
    A('</tbody></table></div>')
    A('<h3>Structured data types</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Schema.org types (JSON-LD)</th></tr></thead><tbody>')
    for b in order:
        A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td><div class="chips">'
          + "".join(f'<span class="chip">{esc(t)}</span>' for t in pages[b].get("schema_types") or []) + '</div></td></tr>')
    A('</tbody></table></div>')
    if qual:
        A('<h3>Content quality signals</h3><div class="tbl"><table><thead><tr><th>Page</th><th class="num">Quality score</th><th class="num">Words</th>'
          '<th class="num">FAQs</th><th class="num">Tables</th><th>E-E-A-T</th><th>Freshness</th></tr></thead><tbody>')
        from report_core import map_get
        for b in order:
            q = map_get(qual, b, {}) or {}
            A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td class="num">{q.get("quality_score", "—")}</td>'
              f'<td class="num">{int(q.get("word_count") or 0):,}</td><td class="num">{q.get("faqs", "—")}</td><td class="num">{q.get("tables", "—")}</td>'
              f'<td>{"Yes" if q.get("eeat") else "No"}</td><td>{esc(q.get("freshness") or "")}</td></tr>')
        A('</tbody></table></div>')
        if c["kpis"].get("word_count_note"):
            A(f'<p class="note">{esc(c["kpis"]["word_count_note"])}</p>')
    A('</section>')


def keywords(h):
    c, A = h.c, h.A
    order, pages, topic = c["order"], c["pages"], c["topic"]
    h.section("keywords", "Keywords", f'How the target phrase <b>“{esc(topic)}”</b> is used in the elements search engines weigh most. '
                                      '✓ = every word of the phrase appears.')
    kc = {b: keyword_checks(pages[b], topic) for b in order}
    A('<div class="tbl"><table class="mx"><thead><tr><th>Placement</th>' + h.th_brands() + '</tr></thead><tbody>')
    for label, key in (("Title tag", "title"), ("Meta description", "meta"), ("H1", "h1"), ("URL", "url"), ("First 100 words", "first100")):
        A(f'<tr><td class="rowh">{label}</td>' + "".join(h.yes(kc[b][key], b) for b in order) + '</tr>')
    A('<tr><td class="rowh">H2/H3 headings containing it</td>' + "".join(f'<td class="c{h.you(b)}">{kc[b]["subheads"]} of {kc[b]["subheads_total"]}</td>' for b in order) + '</tr>')
    A('<tr><td class="rowh">Exact phrase in body</td>' + "".join(f'<td class="c{h.you(b)}">{kc[b]["exact_body"]}</td>' for b in order) + '</tr>')
    A('<tr><td class="rowh">Exact phrase per 1,000 words</td>' + "".join(f'<td class="c{h.you(b)}">{kc[b]["per_1000"]}</td>' for b in order) + '</tr>')
    A('</tbody></table></div>')
    A('<h3>Title, meta description and H1 (verbatim)</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Title</th><th>Meta description</th><th>H1</th></tr></thead><tbody>')
    for b in order:
        p = pages[b]
        t, d = p.get("title") or "", p.get("meta_description") or ""
        A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td>{esc(t)}<small class="muted"> · {len(t)} chars</small></td>'
          f'<td>{esc(d)}<small class="muted"> · {len(d)} chars</small></td><td>{esc(p.get("h1") or "—")}</td></tr>')
    A('</tbody></table></div>')
    auth = c["auth_by"]
    A('<h3>Ranking keywords by page (Ahrefs)</h3>')
    if auth:
        vol, pos = {}, {}
        for b in order:
            for k in (auth.get(b) or {}).get("top_keywords") or []:
                kw = k.get("keyword")
                vol[kw] = max(vol.get(kw) or 0, k.get("volume") or 0)
                pos[(kw, b)] = k.get("position")
        kws = sorted(vol, key=lambda k: -vol[k])[:25]
        if kws:
            A(f'<p class="note" style="margin-top:-4px">Google {esc((c["auth"] or {}).get("country", ""))} positions for keywords each page ranks for (lower is better); — = not ranking. '
              'Volume = monthly searches.</p><div class="tbl"><table class="mx"><thead><tr><th>Keyword</th><th class="num">Volume</th>' + h.th_brands() + '</tr></thead><tbody>')
            for k in kws:
                A(f'<tr><td>{esc(k)}</td><td class="num">{fnum(vol[k])}</td>' + "".join(f'<td class="c{h.you(b)}">{pos.get((k, b)) or "<span class=no>—</span>"}</td>' for b in order) + '</tr>')
            A('</tbody></table></div>')
        else:
            A('<p class="note">None of these pages ranks for any keyword in Ahrefs’ index yet.</p>')
    else:
        h.unavailable("Ahrefs was not connected for this report.", "the keywords each page ranks for, with Google position and monthly search volume.")
    qs, best = serp_matrix(c["ranking"])
    if qs:
        A('<h3>Search ranking by query (web search)</h3><div class="tbl"><table class="mx"><thead><tr><th>Query</th>' + h.th_brands() + '</tr></thead><tbody>')
        for q in qs:
            A(f'<tr><td>{esc(q)}</td>' + "".join(f'<td class="c{h.you(b)}">{best.get((q, b)) or "<span class=no>—</span>"}</td>' for b in order) + '</tr>')
        note = ((c["gaps"].get("serp") or {}).get("note") or "")
        A(f'</tbody></table></div><p class="note">Position in the top results; — = not found. {esc(note)}</p>')
    A('</section>')


def visibility(h):
    c, A = h.c, h.A
    order, auth = c["order"], c["auth_by"]
    h.section("visibility", "Search visibility &amp; authority")
    if auth:
        A(f'<p class="lede">Ahrefs Site Explorer for each exact URL (Domain Rating for the whole site), {esc((c["auth"] or {}).get("country", ""))} database, '
          f'{esc(((c["auth"] or {}).get("fetched_at") or "")[:10])}.</p>')
        A('<div class="tbl"><table><thead><tr><th>Page</th><th class="num">URL Rating</th><th class="num">Domain Rating</th>'
          '<th class="num">Organic traffic<em>monthly</em></th><th class="num">Keywords<em>top 100</em></th><th class="num">Keywords<em>top 3</em></th>'
          '<th class="num">Referring domains</th><th class="num">Backlinks</th></tr></thead><tbody>')
        for b in order:
            a = auth.get(b) or {}
            A(f'<tr{h.trc(b)}><td>{esc(b)}</td>' + "".join(f'<td class="num">{fnum(a.get(k))}</td>' for k in
              ("url_rating", "domain_rating", "org_traffic", "org_keywords", "org_keywords_top3", "refdomains", "backlinks")) + '</tr>')
        A('</tbody></table></div><p class="note">URL Rating and Domain Rating: backlink strength on Ahrefs’ 0–100 scale. '
          'Organic traffic is Ahrefs’ estimate of monthly visits from Google.</p>')
    else:
        h.unavailable("Ahrefs was not connected for this report.",
                      "URL Rating, Domain Rating, organic traffic, ranking keywords (top 100 and top 3), referring domains and backlinks for each page.")
    qs, _ = serp_matrix(c["ranking"])
    top = [r for r in c["ranking"].get("ranking_pages") or [] if r.get("query") == (qs[0] if qs else None)][:10]
    A('<div class="two"><div>')
    if top:
        A(f'<h3>Top results: “{esc(qs[0])}”</h3><div class="tbl"><table><thead><tr><th class="num">#</th><th>Result</th><th>Same page type</th></tr></thead><tbody>')
        for r in top:
            dom = r.get("domain") or r.get("brand")
            A(f'<tr{h.trc(dom)}><td class="num">{r.get("rank")}</td><td>{esc(dom)}<small class="muted" style="display:block">{esc((r.get("title") or "")[:90])}</small></td>'
              f'<td>{"Yes" if r.get("same_type") else "No"}</td></tr>')
        A('</tbody></table></div>')
    A('</div><div><h3>External sources and brands cited</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Mentions</th></tr></thead><tbody>')
    from report_core import map_get
    for b in order:
        ex = map_get(c["gaps"].get("external_brands") or {}, b, []) or []
        A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td>{esc("; ".join(ex)) or "<span class=muted>None</span>"}</td></tr>')
    A('</tbody></table></div></div></div>')
    if c["gaps"].get("ranking_assessment"):
        A('<h3>Ranking assessment</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Google</th><th>AI search</th></tr></thead><tbody>')
        for b in order:
            a = map_get(c["gaps"]["ranking_assessment"], b, {}) or {}
            A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td>{esc(a.get("google") or "")}</td><td>{esc(a.get("ai_search") or "")}</td></tr>')
        A('</tbody></table></div>')
    A('</section>')


def headings(h):
    c, A = h.c, h.A
    order, your, pages, hc, tree = c["order"], c["your"], c["pages"], c["hcounts"], c["tree"]
    h.section("headings", "Heading structure", "Every H1–H4 heading on the pages, merged into one hierarchy. Differently punctuated headings are matched; "
                                               "✓ means that heading exists on that page.")
    A('<div class="tbl"><table class="mx"><thead><tr><th>Heading level</th>' + h.th_brands() + '</tr></thead><tbody>')
    for l in (1, 2, 3, 4):
        A(f'<tr><td class="rowh">H{l}</td>' + "".join(f'<td class="c{h.you(b)}">{hc[b][l]}</td>' for b in order) + '</tr>')
    A('</tbody></table></div>')
    y, comps = hc[your], order[1:]
    m2, m3 = median([hc[b][2] for b in comps]), median([hc[b][3] for b in comps])
    A(f'<div class="callout"><b>Your page:</b> {y[1]} H1 (“{esc(pages[your].get("h1") or "")}”), {y[2]} H2, {y[3]} H3, {y[4]} H4. '
      f'Competitor median: {m2:g} H2 and {m3:g} H3.</div>' if m2 is not None else '')
    miss = sum(1 for r in tree if not r["present"][your] and sum(r["present"].values()) >= 2)
    A(f'<h3>Heading hierarchy: H1 › H2 › H3 › H4 ({len(tree):,} headings)</h3>'
      f'<p class="note" style="margin-top:-4px">{miss} headings are used by two or more competitors but not by your page.</p>')
    h.filterbar("hier", [("all", "All"), ("miss", "Missing on your page"), ("shared", "Used by 2+ pages")])
    A('<div class="tbl scroll"><table class="mx tree" id="hier"><thead><tr><th>Heading</th>' + h.th_brands() + '</tr></thead><tbody>')
    for r in tree:
        A(f'<tr data-you="{int(r["present"][your])}" data-n="{sum(r["present"].values())}" class="lv{r["level"]}"><td class="h"><span class="tag">H{r["level"]}</span>{esc(r["text"])}</td>'
          + "".join(h.yes(r["present"][b], b) for b in order) + '</tr>')
    A('</tbody></table></div>')
    nih = c["not_in_headings"]
    A('<h3>Topics styled as headings but not marked up as H-tags</h3>')
    if any(nih.values()):
        A('<div class="tbl"><table><thead><tr><th>Page</th><th>Text shown as a title</th><th>Current tag</th><th>Under heading</th><th>Should be</th></tr></thead><tbody>')
        for b in order:
            for r in nih[b]:
                A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td>{esc(r["text"])}</td><td>&lt;{esc(r["tag"])}&gt;</td>'
                  f'<td>{esc(r["parent_heading"])}</td><td>{r["suggested"]}</td></tr>')
        A('</tbody></table></div>')
    else:
        A('<p class="note">None found: every visual section title on these pages uses a real heading tag.</p>')
    sf = c["gaps"].get("structure_fix") or {}
    probs = [p for _, p in c["structure_problems"]] + [esc(p) for p in sf.get("problems") or []]
    if probs or sf.get("title_recommendation") or sf.get("h1_recommendation"):
        A('<h3>Structure issues on your page</h3><ul class="findings">' + "".join(f'<li><b>Issue</b><span>{p}</span></li>' for p in probs))
        if sf.get("title_recommendation"):
            A(f'<li><b>Title</b><span>{esc(sf["title_recommendation"])}</span></li>')
        if sf.get("h1_recommendation"):
            A(f'<li><b>H1</b><span>{esc(sf["h1_recommendation"])}</span></li>')
        A('</ul>' + (f'<p class="note">{esc(sf["notes"])}</p>' if sf.get("notes") else ""))
    A('<h3>Page structure: every heading and its content, in page order</h3>')
    if h.p:
        A('<p class="note">Full heading-by-heading content for every page is in the HTML report and XLSX → Page Structure.</p>')
    else:
        for b in order:
            secs = [s for s in pages[b].get("sections") or [] if s.get("heading") and s.get("heading") != "(intro)"]
            body = '<ol class="struct">' + "".join(
                f'<li class="lv{min(max(int(s.get("level") or 1), 1), 4)}"><div class="t"><span class="tag">H{int(s.get("level") or 0)}</span>{esc(s.get("heading"))}</div>'
                f'<p class="x">{esc(s.get("text") or "")}</p></li>' for s in secs) + '</ol>'
            h.details(f'<b>{esc(b)}</b><span class="muted">{len(secs)} sections · H1 {hc[b][1]} · H2 {hc[b][2]} · H3 {hc[b][3]} · H4 {hc[b][4]}</span>', body)
    A('</section>')


def topics(h):
    c, A = h.c, h.A
    order, your, kpi = c["order"], c["your"], c["kpis"]
    h.section("topics", "Topic coverage &amp; gaps", esc(kpi.get("coverage_basis") or ""))
    A('<div class="kpis">'
      f'<div class="kpi"><div class="l">Coverage</div><div class="v">{kpi.get("coverage_pct", "—")}%</div><div class="s">{len(c["topics"])} topics compared</div></div>'
      f'<div class="kpi"><div class="l">Missing · Thin</div><div class="v">{kpi.get("missing_count", 0)}<small> · {kpi.get("thin_count", 0)}</small></div><div class="s">Topics to add or deepen</div></div>'
      f'<div class="kpi"><div class="l">FAQ gaps</div><div class="v">{kpi.get("faq_gap_count", 0)}</div><div class="s">Competitor questions you don’t answer</div></div>'
      f'<div class="kpi"><div class="l">Unique to you</div><div class="v">{kpi.get("unique_count", 0)}</div><div class="s">Topics only your page covers</div></div></div>')
    A('<h3>Coverage by topic: heading level used and depth</h3><p class="note" style="margin-top:-4px">Cell = heading level of the section covering the topic '
      '(Body = in text with no dedicated heading), then depth. — = not covered. Select a topic for the exact content.</p>')
    h.filterbar("topicsm", [("all", "All topics"), ("miss", "Missing on your page"), ("shared", "Covered by 2+ pages")])
    A('<div class="tbl"><table class="mx" id="topicsm"><thead><tr><th>Topic</th>' + h.th_brands() + '</tr></thead><tbody>')
    for i, t in enumerate(c["topics"]):
        cells = []
        for b in order:
            v = t["brands"][b]
            d = int(v["info"].get("depth", 0) or 0)
            cells.append(f'<td class="c{h.you(b)}">' + (f'<span class="tag">{v["tag"]}</span><small class="dp">{DEPTH_LABEL.get(d, "")}</small>'
                                                        if v["present"] else '<span class=no>—</span>') + '</td>')
        A(f'<tr data-you="{int(t["brands"][your]["present"])}" data-n="{sum(v["present"] for v in t["brands"].values())}">'
          f'<td><a href="#t{i}">{esc(t["name"])}</a><small class="muted"> · {esc(t["intent"])}</small></td>{"".join(cells)}</tr>')
    A('</tbody></table></div>')
    if any(v["source"] == "matched" for t in c["topics"] for v in t["brands"].values()):
        A('<p class="note">Heading levels marked here were matched automatically from heading and section text; '
          'runs analysed with plugin v0.7+ record the exact heading per page.</p>')
    A('<h3>Unique coverage: topics only one page covers</h3><div class="tbl"><table><thead><tr><th>Page</th><th>Topics</th></tr></thead><tbody>')
    for b in order:
        A(f'<tr{h.trc(b)}><td class="nowrap">{esc(b)}</td><td>{esc("; ".join(c["unique"].get(b) or [])) or "<span class=muted>None</span>"}</td></tr>')
    A('</tbody></table></div>')
    A(f'<h3>Prioritised gaps ({len(c["gap_list"])})</h3>' + (f'<p class="note" style="margin-top:-4px">{esc(kpi.get("priority_method"))}</p>' if kpi.get("priority_method") else ""))
    for g in c["gap_list"]:
        p = PRIORITY_LABEL.get(int(g.get("priority") or 0), "")
        A(f'<details class="gap"{" open" if h.p else ""}><summary><span><span class="pill {p.lower()}">{p}</span></span><span>{esc((g.get("type") or "").title())}</span>'
          f'<span style="color:var(--ink)">{esc(g.get("title"))}</span><span class="sb muted">{esc(g.get("exemplar_brand") or "")}</span></summary>'
          f'<div class="body"><p>{esc(g.get("detail") or "")}</p>' + (f'<p><b>Recommendation:</b> {esc(g.get("recommendation"))}</p>' if g.get("recommendation") else "")
          + '</div></details>')
    A('</section>')


def content(h):
    c, A = h.c, h.A
    order, your = c["order"], c["your"]
    h.section("content", "Content by topic", "For every topic: the heading each page uses, how deep it goes, and the exact text under that heading. "
                                             "Similarity compares each competitor’s text with yours.")
    A('<div class="tools noprint"><button class="btn" onclick="accAll(\'#content-topics\',true)">Expand all</button>'
      '<button class="btn" onclick="accAll(\'#content-topics\',false)">Collapse all</button></div><div id="content-topics">')
    for i, t in enumerate(c["topics"]):
        yours = ((t["brands"][your]["sec"] or {}).get("text") or "")
        cov = [b for b in order if t["brands"][b]["present"]]
        yv = t["brands"][your]
        status = f'Your page: {yv["tag"]} · {DEPTH_LABEL.get(int(yv["info"].get("depth", 0) or 0), "")}' if yv["present"] else "Not on your page"
        cards = []
        for b in order:
            v = t["brands"][b]
            head = f'<div class="ch"><b>{esc(b)}</b>'
            if not v["present"]:
                cards.append(f'<div class="card absent">{head}</div><p class="muted">Not covered on this page.</p></div>')
                continue
            info, sec = v["info"], v["sec"]
            flags = [DEPTH_LABEL.get(int(info.get("depth", 0) or 0), ""), f'{int(info.get("word_count") or 0):,} words']
            flags += [x for x, k in (("example", "has_example"), ("table", "has_table")) if info.get(k)]
            text = (sec or {}).get("text") or ""
            if sec and v["tag"] == "Body":
                hd = f'<div class="hd"><span class="tag">Body</span><span class="muted" style="font-weight:400">No dedicated heading; in the text under “{esc(sec.get("heading") or "")}”</span></div>'
            elif sec:
                hd = f'<div class="hd"><span class="tag">{v["tag"]}</span>{esc(sec.get("heading") or "")}</div>'
            else:
                hd = '<div class="hd"><span class="tag">Body</span><span class="muted" style="font-weight:400">No dedicated heading</span></div>'
            sim = ""
            if b != your and text and yours:
                pct = similarity(yours, text)
                sim = f'<span class="sim">Similarity to yours: {pct}% · {sim_verdict(pct)}</span>'
            cards.append(f'<div class="card{" yours" if b == your else ""}">{head}<span class="muted">{" · ".join(f for f in flags if f)}</span></div>{hd}'
                         f'<p class="sum"><span>Summary</span>{esc(info.get("snippet") or "")}</p>'
                         + (f'<div class="text">{esc(text)}</div>' if text else '<p class="muted">Section text not captured.</p>') + f'{sim}</div>')
        A(f'<details class="acc topic" id="t{i}"{" open" if h.p else ""}><summary><b>{esc(t["name"])}</b>'
          f'<span class="muted">{len(cov)} of {len(order)} pages · {status}</span></summary><div class="cards">{"".join(cards)}</div></details>')
    A('</div></section>')


def faqs(h):
    c, A = h.c, h.A
    order, your, pages, rows = c["order"], c["your"], c["pages"], c["faq_rows"]
    ours = sum(r["present"][your] for r in rows)
    h.section("faqs", "FAQs", f'{len(rows)} distinct questions across the pages; your page answers {ours}. Differently worded questions on the same point are grouped.')
    A('<div class="tbl"><table class="mx"><thead><tr><th></th>' + h.th_brands() + '</tr></thead><tbody><tr><td class="rowh">Questions on page</td>'
      + "".join(f'<td class="c{h.you(b)}">{len(pages[b].get("faqs") or [])}</td>' for b in order) + '</tr><tr><td class="rowh">FAQPage schema</td>'
      + "".join(h.yes("FAQPage" in (pages[b].get("schema_types") or []), b) for b in order) + '</tr></tbody></table></div>')
    fg = c["gaps"].get("faq_gaps") or []
    if fg:
        from report_core import _norm
        A(f'<h3>Questions competitors answer and you don’t ({len(fg)})</h3><div class="tbl"><table class="mx"><thead><tr><th>Question</th>' + h.th_brands() + '</tr></thead><tbody>')
        for f in fg:
            ab = {_norm(x) for x in f.get("answered_by") or []}
            A(f'<tr><td>{esc(f.get("question"))}</td>' + "".join(h.yes(_norm(b) in ab, b) for b in order) + '</tr>')
        A('</tbody></table></div>')
    A('<h3>All questions by page</h3>')
    h.filterbar("faqm", [("all", "All questions"), ("miss", "Not answered by you"), ("shared", "Answered by 2+ pages")])
    A('<div class="tbl scroll"><table class="mx" id="faqm"><thead><tr><th>Question</th>' + h.th_brands() + '</tr></thead><tbody>')
    for r in rows:
        A(f'<tr data-you="{int(r["present"][your])}" data-n="{sum(r["present"].values())}"><td>{esc(r["question"])}</td>' + "".join(h.yes(r["present"][b], b) for b in order) + '</tr>')
    A('</tbody></table></div><h3>Questions and answers as published</h3>')
    from report_core import clean_text
    for b in order:
        fq = pages[b].get("faqs") or []
        body = ('<ol class="faq">' + "".join(f'<li><p class="q">{esc(f.get("question") or "")}</p><p class="a">{esc(clean_text(f.get("answer") or ""))}</p></li>' for f in fq) + '</ol>'
                if fq else '<p class="muted" style="padding:0 14px 12px">This page has no FAQ section.</p>')
        h.details(f'<b>{esc(b)}</b><span class="muted">{len(fq)} questions</span>', body)
    A('</section>')


def links(h):
    c, A = h.c, h.A
    order, pages, qual = c["order"], c["pages"], c["quality"]
    h.section("links", "Links &amp; images", "Internal links are on-page editorial links; navigation, header and footer links are excluded.")
    A('<div class="tbl"><table class="mx"><thead><tr><th></th>' + h.th_brands() + '</tr></thead><tbody>')
    for label, fn in (("Internal links (article body)", lambda b: internal_link_count(pages[b], qual)),
                      ("Unique internal targets", lambda b: pages[b].get("unique_internal_targets")),
                      ("External links", lambda b: pages[b].get("external_link_count")), ("Images", lambda b: pages[b].get("image_count"))):
        A(f'<tr><td class="rowh">{label}</td>' + "".join(f'<td class="c{h.you(b)}">{fnum(fn(b))}</td>' for b in order) + '</tr>')
    A('</tbody></table></div>')
    lg = c["gaps"].get("link_gaps") or []
    if lg:
        from report_core import _norm
        A(f'<h3>Internal-link gaps ({len(lg)})</h3><div class="tbl"><table class="mx"><thead><tr><th>Link target competitors use</th>' + h.th_brands() + '</tr></thead><tbody>')
        for l in lg:
            pi = {_norm(x) for x in l.get("present_in") or []}
            A(f'<tr><td>{esc(l.get("topic_or_target"))}</td>' + "".join(h.yes(_norm(b) in pi, b) for b in order) + '</tr>')
        A('</tbody></table></div>')
    A('<h3>Links per page</h3>')
    if h.p:
        A('<p class="note">Every link with anchor text and section is in the HTML report and XLSX → Links.</p>')
    else:
        for b in order:
            il, el = onpage_internal_links(pages[b]), pages[b].get("external_links") or []
            rows = "".join(f'<tr><td>{kind}</td><td>{esc(l.get("anchor") or "")}</td><td>{esc(l.get("href") or "")}</td><td>{esc(l.get("section") or "")}</td></tr>'
                           for kind, ls in (("Internal", il), ("External", el)) for l in ls)
            h.details(f'<b>{esc(b)}</b><span class="muted">{len(il)} internal · {len(el)} external</span>',
                      '<div class="tbl inner"><table class="linktbl"><thead><tr><th>Type</th><th>Anchor text</th><th>URL</th><th>Section</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></div>')
    A('<h3>Images per page</h3>')
    if h.p:
        A('<p class="note">Every image with its alt text is in the HTML report and XLSX → Images.</p>')
    else:
        for b in order:
            im = pages[b].get("images") or []
            rows = "".join(f'<tr><td>{esc(i.get("alt") or "") or "<span class=muted>(none)</span>"}</td><td>{esc(i.get("src") or "")}</td></tr>' for i in im)
            h.details(f'<b>{esc(b)}</b><span class="muted">{len(im)} images · {sum(1 for i in im if not (i.get("alt") or "").strip())} without alt text</span>',
                      f'<div class="tbl inner"><table class="linktbl"><thead><tr><th>Alt text</th><th>Image</th></tr></thead><tbody>{rows}</tbody></table></div>')
    A('</section>')


def actions(h):
    c, A = h.c, h.A
    h.section("actions", "Recommendations", "Highest-priority gaps with the recommended fix and the competitor page that does it best. "
                                             "Page-speed fixes are listed in section 2.")
    A('<div class="tbl"><table><thead><tr><th class="num">#</th><th>Priority</th><th>Area</th><th>Action</th><th>Best example</th></tr></thead><tbody>')
    top = [g for g in c["gap_list"] if g.get("recommendation")]
    top = [g for g in top if int(g.get("priority") or 0) == 3] or top[:10]
    for i, g in enumerate(top, 1):
        p = PRIORITY_LABEL.get(int(g.get("priority") or 0), "")
        A(f'<tr><td class="num">{i}</td><td><span class="pill {p.lower()}">{p}</span></td><td class="nowrap">{esc((g.get("type") or "").title())}</td>'
          f'<td><b style="color:var(--ink)">{esc(g.get("title"))}</b><br>{esc(g.get("recommendation"))}</td><td class="nowrap">{esc(g.get("exemplar_brand") or "")}</td></tr>')
    A('</tbody></table></div></section>')


def method(h):
    c, A = h.c, h.A
    psi, auth = c["psi"], c["auth"]
    rows = [("Page crawl (raw HTML)", "Headings, section content, FAQs, links, images, meta tags, structured data", "Collected"),
            ("Gap analysis", "Topic clustering, depth, gaps, priorities, quality signals", "Collected"),
            ("Web search", "Competitor discovery and ranking check", "Collected" if c["ranking"] else "Not run"),
            ("Google PageSpeed Insights API v5", "Core Web Vitals (CrUX real users), Lighthouse lab metrics and scores",
             f'Collected {(psi.get("fetched_at") or "")[:10]} · {psi.get("summary", {}).get("succeeded", "?")}/{psi.get("summary", {}).get("requested", "?")} measurements' if psi else "Not available yet"),
            ("Ahrefs API v3 (Site Explorer)", "URL/Domain Rating, backlinks, referring domains, organic traffic and keywords",
             f'Collected {(auth.get("fetched_at") or "")[:10]} · {auth.get("country", "")} database' if auth else "Not available yet"),
            ("Semrush", "Additional keyword and traffic data", "Not included")]
    h.section("method", "Method &amp; data sources", pb=False)
    A('<div class="tbl"><table><thead><tr><th>Source</th><th>What it provides</th><th>Status</th></tr></thead><tbody>'
      + "".join(f'<tr><td>{a}</td><td>{b}</td><td>{esc(s)}</td></tr>' for a, b, s in rows) + '</tbody></table></div>'
      '<p class="note">Thresholds: Google Core Web Vitals (LCP 2.5 s / 4.0 s, INP 200 ms / 500 ms, CLS 0.10 / 0.25) and Lighthouse scoring. '
      'Content analysis describes gaps and briefs only; it never produces publishable copy.</p></section>')
