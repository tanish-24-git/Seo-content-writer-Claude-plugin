"""HTML renderer: a self-contained, comparison-only competitive content report.

render(ctx, print_mode=False) -> str

Layout: a fixed sidebar index (sections + one entry per compared page) and a
white / blue reading column. Every section states what each page has — search
visibility, page speed and Lighthouse scores, on-page SEO, H1-H4 structure,
topic coverage, the content each page wrote side by side, FAQs, figures and
claims — and a full detail view per page (outline, verbatim content by section,
FAQs, examples, links, images). The report compares; it does not recommend.

Standard library only; no external CSS, fonts or scripts.
"""
import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from report_core import _load, clean_text, esc, internal_link_count, keyword_checks, onpage_internal_links, rate

DEPTH = {3: ("Deep", "d3"), 2: ("Standard", "d2"), 1: ("Mention", "d1"), 0: ("—", "d0")}
INTENT = {"high": "High-value topics", "medium": "Supporting topics", "low": "Background topics"}
CATS = (("performance", "Performance"), ("accessibility", "Accessibility"), ("best-practices", "Best practices"), ("seo", "SEO"))
LAB = (("lcp_ms", "LCP", "Largest Contentful Paint"), ("cls", "CLS", "Cumulative Layout Shift"),
       ("tbt_ms", "TBT", "Total Blocking Time"), ("fcp_ms", "FCP", "First Contentful Paint"),
       ("si_ms", "Speed Index", "Speed Index"), ("ttfb_ms", "TTFB", "Server response time"),
       ("bytes", "Page weight", "Total transfer size"))
STATUS = {"good": "Good", "ni": "Needs improvement", "poor": "Poor"}

CSS = """
:root{--navy:#0A2F5C;--blue:#005BAA;--blue2:#3F8FD8;--sky:#EEF5FC;--sky2:#DCEAF8;--line:#DCE5F0;--ink:#1F2937;
--muted:#5B6B80;--yellow:#E8A800;--ysoft:#FFF7DB;--good:#1E7F4F;--gbg:#E7F5EE;--ni:#9A6700;--nbg:#FFF4D6;--poor:#B42318;--pbg:#FDECEA;--side:290px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:16px}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.6 "Segoe UI",Calibri,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.side{position:fixed;inset:0 auto 0 0;width:var(--side);background:var(--sky);border-right:1px solid var(--line);overflow-y:auto;padding:22px 0 40px}
.side .rt{padding:0 22px 16px;border-bottom:1px solid var(--line);margin-bottom:10px}
.side .rt b{display:block;color:var(--navy);font-size:15px;line-height:1.35}.side .rt span{color:var(--muted);font-size:12.5px}
.side h6{margin:16px 22px 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
.side a{display:flex;gap:10px;align-items:baseline;padding:6px 22px 6px 19px;color:var(--navy);font-size:14px;border-left:3px solid transparent}
.side a .no{color:var(--muted);font-size:12px;min-width:18px}
.side a:hover{background:var(--sky2);text-decoration:none}.side a.on{background:#fff;border-left-color:var(--yellow);font-weight:600}
.side a.sub{padding-left:47px;font-size:13.5px}
main{margin-left:var(--side);padding:0 48px 80px;max-width:calc(1240px + var(--side))}
.top{padding:34px 0 22px;border-bottom:2px solid var(--sky2);margin-bottom:8px}
.top .k{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);font-weight:600}
.top h1{margin:6px 0 6px;color:var(--navy);font-size:30px;line-height:1.25}
.top p{margin:2px 0;color:var(--muted)}
section{padding:30px 0 10px;border-bottom:1px solid var(--line)}section:last-of-type{border-bottom:0}
h2{color:var(--navy);font-size:23px;margin:0 0 4px}h2 .n{color:var(--blue);margin-right:8px}
.lede{color:var(--muted);margin:0 0 18px;max-width:900px}
h3{color:var(--navy);font-size:17px;margin:26px 0 10px}h4{color:var(--navy);font-size:15px;margin:18px 0 8px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:8px 0 16px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
thead th{background:var(--navy);color:#fff;font-weight:600;font-size:13px;position:sticky;top:0;z-index:1}
thead th.us{background:var(--blue);box-shadow:inset 0 -3px 0 var(--yellow)}
table.cmp{table-layout:fixed}table.cmp th:first-child{width:26%}table.cmp th.xtra{width:9%}
tbody tr:nth-child(even) td{background:#FAFCFE}tbody tr:last-child td{border-bottom:0}
td.lab{font-weight:600;color:var(--navy);background:var(--sky)!important;overflow-wrap:anywhere}
td.us{background:var(--ysoft)!important}td.c,th.c{text-align:center}td.num{text-align:right;font-variant-numeric:tabular-nums}
.small{font-size:12.5px;color:var(--muted)}.mono{font-family:Consolas,"Courier New",monospace;font-size:12px;word-break:break-all}
.pill{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.good{background:var(--gbg);color:var(--good)}.ni{background:var(--nbg);color:var(--ni)}.poor{background:var(--pbg);color:var(--poor)}
.na{background:#F1F4F8;color:var(--muted)}.blue{background:var(--sky2);color:var(--navy)}
.us-tag{display:inline-block;margin-left:6px;padding:0 7px;border-radius:4px;background:var(--yellow);color:#3A2A00;font-size:10.5px;font-weight:700;letter-spacing:.04em;vertical-align:2px}
.d3{background:var(--blue)!important;color:#fff;font-weight:600}.d2{background:#BFD7F1!important;color:var(--navy)}
.d1{background:var(--sky2)!important;color:var(--navy)}.d0{color:#9AA7B6}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:6px 0 18px}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#fff}
.card .v{font-size:26px;font-weight:700;color:var(--navy);line-height:1.2}.card .l{font-size:13px;color:var(--muted)}
.card.us{border-color:var(--yellow);background:var(--ysoft)}
.obs{margin:6px 0 18px;padding:0;list-style:none}.obs li{padding:9px 14px;border-left:3px solid var(--blue);background:var(--sky);margin:0 0 8px;border-radius:0 6px 6px 0}
.tools{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px}
.btn{border:1px solid var(--line);background:#fff;color:var(--navy);padding:5px 12px;border-radius:6px;font:inherit;font-size:13px;cursor:pointer}
.btn.on,.btn:hover{background:var(--navy);color:#fff;border-color:var(--navy)}
input.q{border:1px solid var(--line);border-radius:6px;padding:6px 10px;font:inherit;font-size:13.5px;min-width:280px}
details.topic{border:1px solid var(--line);border-radius:10px;margin:0 0 12px;background:#fff}
details.topic>summary{cursor:pointer;list-style:none;padding:12px 16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
details.topic>summary::-webkit-details-marker{display:none}
details.topic>summary b{color:var(--navy);font-size:15.5px;margin-right:auto}
details.topic[open]>summary{border-bottom:1px solid var(--line);background:var(--sky);border-radius:10px 10px 0 0}
.chip{font-size:11.5px;padding:1px 8px;border-radius:4px;border:1px solid var(--line)}
.row{display:grid;grid-template-columns:200px 1fr;gap:18px;padding:14px 16px;border-bottom:1px solid var(--line)}.row:last-child{border-bottom:0}
.row.us{background:var(--ysoft)}.row .who b{color:var(--navy);display:block}.row .who .small{display:block;margin-top:2px}
.sum{margin:0 0 10px;color:var(--ink)}.cap{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:0 0 3px}.quote{margin:0;padding:10px 14px;background:#F7FAFD;border:1px solid var(--line);border-radius:6px;font-size:14px;white-space:pre-line}
.quote.more{margin-top:6px}.nc{color:var(--muted);font-style:italic}
details.more>summary{cursor:pointer;color:var(--blue);font-size:13px;margin-top:6px}
.grid5{display:grid;grid-template-columns:repeat(5,minmax(200px,1fr));gap:12px;overflow-x:auto}
.col{border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:200px}.col.us{border-color:var(--yellow);background:var(--ysoft)}
.col h4{margin:0 0 8px}
.ol{list-style:none;margin:0;padding:0}.ol li{padding:3px 0;font-size:13.5px;display:flex;gap:8px}
.tag{flex:none;font-size:10.5px;font-weight:700;padding:1px 5px;border-radius:3px;background:var(--sky2);color:var(--navy);height:fit-content;margin-top:2px}
.tag.h1{background:var(--navy);color:#fff}.tag.h2{background:var(--blue);color:#fff}
.ol li.l3{padding-left:18px}.ol li.l4{padding-left:36px}.ol li.l5,.ol li.l6{padding-left:54px}
.pg-head{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline;margin-bottom:6px}
.kv{display:grid;grid-template-columns:190px 1fr;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:8px 0 16px}
.kv div{padding:8px 12px;border-bottom:1px solid var(--line)}.kv div:nth-child(odd){background:var(--sky);font-weight:600;color:var(--navy)}
.kv div:nth-last-child(-n+2){border-bottom:0}
.sec{margin:0 0 14px;padding:0 0 12px;border-bottom:1px dashed var(--line)}.sec:last-child{border-bottom:0}
.sec h5{margin:0 0 6px;font-size:15px;color:var(--navy);display:flex;gap:8px;align-items:baseline}
.sec p{margin:0;max-width:980px;white-space:pre-line}
.faq{border:1px solid var(--line);border-radius:8px;margin:0 0 8px}.faq summary{cursor:pointer;padding:9px 14px;font-weight:600;color:var(--navy)}
.faq div{padding:0 14px 12px;max-width:980px}
.cols2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
ul.plain{margin:6px 0 0;padding-left:18px}ul.plain li{margin:0 0 4px}
.foot{margin-top:40px;color:var(--muted);font-size:12.5px}
.menu{display:none}
@media (max-width:980px){.side{position:static;width:auto;border-right:0;border-bottom:1px solid var(--line);max-height:none}
main{margin-left:0;padding:0 16px 60px}.row{grid-template-columns:1fr}.kv{grid-template-columns:1fr}}
@media print{.side,.tools,.menu{display:none!important}main{margin:0;padding:0;max-width:none}details{break-inside:avoid}
thead th{position:static}section{break-before:page}a{color:var(--ink)}}
"""

JS = """
(function(){
var links=[].slice.call(document.querySelectorAll('.side a[href^="#"]'));
var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
var obs=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
links.forEach(function(a){a.classList.remove('on');});var a=map[e.target.id];if(a)a.classList.add('on');}});},{rootMargin:'0px 0px -70% 0px'});
document.querySelectorAll('section[id]').forEach(function(s){obs.observe(s);});
})();
function filt(btn,grp,val){document.querySelectorAll('[data-grp="'+grp+'"] .btn').forEach(function(b){b.classList.remove('on');});btn.classList.add('on');
document.querySelectorAll('[data-'+grp+']').forEach(function(el){var t=el.getAttribute('data-'+grp).split(' ');el.style.display=(val==='all'||t.indexOf(val)>=0)?'':'none';});}
function accAll(sel,open){document.querySelectorAll(sel+' details.topic').forEach(function(d){d.open=open;});}
function search(inp,tbl){var q=inp.value.toLowerCase();document.querySelectorAll('#'+tbl+' tbody tr').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)>=0?'':'none';});}
"""


# ----------------------------------------------------------------------------- helpers
def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _host(url):
    h = (urlparse(url or "").netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def _ms(v):
    return "—" if v is None else (f"{v / 1000:.1f} s" if v >= 1000 else f"{int(v)} ms")


def _metric(key, v):
    if v is None:
        return "—"
    if key == "cls":
        return f"{v:.3f}"
    if key == "bytes":
        return f"{v / 1048576:.1f} MB"
    return _ms(v)


def _pill(text, cls):
    return f'<span class="pill {cls}">{esc(text)}</span>'


# Legal / regulatory boilerplate (disclaimers, fraud warnings, UIN lists) is never quoted as a
# page's coverage of a topic, and form pickers ("4 5 6 ... 82") are not prose.
_LEGAL = re.compile(r"IRDAI|\bUIN\b|risk factors|beware|spurious|fictitious|terms (?:and|&) conditions|"
                    r"disclaimer|formerly known as|registered office|\bCIN\b|trade ?logo", re.I)
_NUM_RUN = re.compile(r"(?:\b\d{1,3}\b[\s,]+){8,}")


def _sec_text(sec):
    if not sec:
        return ""
    t = sec.get("spa_model_text") or clean_text(sec.get("text") or "") or ""
    return re.sub(r"\s{2,}", " ", _NUM_RUN.sub(" … ", t)).strip()


def _quotable(sec):
    """A section whose text can stand for a page's coverage of a topic (not legal boilerplate)."""
    if not sec:
        return False
    blob = (sec.get("heading") or "") + " " + (sec.get("text") or "")[:1500]
    return len(_LEGAL.findall(blob)) < 3


class R:
    def __init__(self, ctx, print_mode):
        self.c, self.p = ctx, print_mode
        self.meta = ctx["meta"]
        self.order, self.you, self.pages = ctx["order"], ctx["your"], ctx["pages"]
        self.names = self.meta.get("display_names") or {}
        self.out = []

    def A(self, s):
        self.out.append(s)

    def name(self, b):
        return self.names.get(b, b)

    def label(self, b):
        return esc(self.name(b)) + ('<span class="us-tag">OUR PAGE</span>' if b == self.you else "")

    def th(self, extra_first=None):
        cells = [f'<th>{esc(extra_first)}</th>'] if extra_first is not None else []
        return "".join(cells) + "".join(f'<th class="c{" us" if b == self.you else ""}">{esc(self.name(b))}</th>' for b in self.order)

    def td(self, b, html_, cls="c"):
        return f'<td class="{cls}{" us" if b == self.you else ""}">{html_}</td>'

    def section(self, sid, num, title, lede=""):
        self.A(f'<section id="{sid}"><h2><span class="n">{num}</span>{esc(title)}</h2>' + (f'<p class="lede">{lede}</p>' if lede else ""))

    def end(self):
        self.A("</section>")

    def pid(self, b):
        return "page-" + (re.sub(r"[^a-z0-9]+", "-", self.name(b).lower()).strip("-") or "x")


# ----------------------------------------------------------------------------- data shaping
def serp_queries(c):
    """[(query, [ {rank, domain, url} ])] from ranking.json (v0.7) or serp.json (per_query)."""
    rk = c.get("ranking") or {}
    if rk.get("per_query"):
        src = rk
    else:
        src = _load(os.path.join(c["run_dir"], "serp.json"), {}) or {}
        if not src.get("per_query"):
            src = rk
    if src.get("per_query"):
        return [(q.get("query") or "", q.get("results") or []) for q in src["per_query"]]
    groups = {}
    for r in src.get("ranking_pages") or []:
        groups.setdefault(r.get("query") or "", []).append(r)
    return list(groups.items())


def brand_domains(c):
    meta, out = c["meta"], {}
    out[c["your"]] = {_host(meta.get("your_url"))} | set(meta.get("your_domains") or [])
    for comp in meta.get("competitors") or []:
        out[comp.get("brand")] = {_host(comp.get("url")), _host(comp.get("user_supplied_url"))} | set(comp.get("domains") or [])
    return {b: {d for d in ds if d} for b, ds in out.items()}


def page_kind(url):
    u = (url or "").lower()
    if re.search(r"blog|insurance-guide|knowledge|article|/guide", u):
        return "article"
    if "calculator" in u:
        return "calculator"
    return "page"


def psi_rec(c, b, device):
    rec = (c.get("psi_by") or {}).get(b) or {}
    r = rec.get(device) or {}
    return None if not r or r.get("error") else r


def topics_covered(c, b, min_depth=2):
    return sum(1 for t in c["topics"] if _int(t["brands"][b]["info"].get("depth")) >= min_depth)


# ----------------------------------------------------------------------------- sections
def nav(h):
    c = h.c
    items = [("summary", "1", "Summary"), ("pages", "2", "Pages compared"), ("visibility", "3", "Search visibility"),
             ("speed", "4", "Page speed & scores"), ("onpage", "5", "On-page SEO"), ("headings", "6", "Heading structure"),
             ("topics", "7", "Topic coverage"), ("content", "8", "Content side by side"), ("faqs", "9", "FAQ comparison"),
             ("claims", "10", "Figures & claims")]
    groups = [("Overview", items[:2]), ("Search & performance", items[2:4]), ("Structure", items[4:6]), ("Content", items[6:])]
    h.A('<nav class="side" aria-label="Report contents"><div class="rt"><b>Competitive Content Comparison</b>'
        f'<span>{esc(c["topic"].title() or "Content comparison")}</span></div>')
    for g, its in groups:
        h.A(f"<h6>{esc(g)}</h6>")
        for sid, n, t in its:
            h.A(f'<a href="#{sid}"><span class="no">{n}</span>{esc(t)}</a>')
    h.A("<h6>Page details</h6>")
    for i, b in enumerate(h.order, 1):
        h.A(f'<a class="sub" href="#{h.pid(b)}">{esc(h.name(b))}{" (ours)" if b == h.you else ""}</a>')
    h.A('<h6>Appendix</h6><a href="#method"><span class="no">A</span>Method &amp; sources</a></nav>')


def header(h):
    c, meta = h.c, h.meta
    date = meta.get("created_at") or datetime.now().strftime("%Y-%m-%d")
    comps = ", ".join(esc(h.name(b)) for b in h.order if b != h.you)
    h.A(f'<div class="top"><div class="k">Competitive content comparison · {esc(c["meta"].get("page_type") or "page")} page</div>'
        f'<h1>{esc((c["topic"] or "Content").title())}: {esc(h.name(h.you))} vs competitors</h1>'
        f'<p>Our page: <a href="{esc(meta.get("your_url"))}" target="_blank" rel="noopener">{esc(meta.get("your_url"))}</a></p>'
        f'<p>Compared with {comps} · Data collected {esc(date)}</p></div>')


def summary(h):
    c = h.c
    h.section("summary", "1", "Summary", "Headline measures for each page. Every figure links to the section that explains it.")
    rows = []
    ntop = len(c["topics"])

    def score(b, dev, cat="performance"):
        r = psi_rec(c, b, dev)
        v = (r or {}).get("scores", {}).get(cat)
        return _pill(v, rate("score", v)) if v is not None else _pill("n/a", "na")

    best_rank = {}
    doms = brand_domains(c)
    for q, res in serp_queries(c):
        if any(d in (q or "").lower() for d in doms.get(h.you, ())):
            continue
        for r in res:
            for b in h.order:
                if any((r.get("domain") or _host(r.get("url"))).endswith(d) for d in doms.get(b, ())):
                    if r.get("rank") and (b not in best_rank or r["rank"] < best_rank[b]):
                        best_rank[b] = r["rank"]

    def line(label, fn, link):
        rows.append(f'<tr><td class="lab"><a href="#{link}">{esc(label)}</a></td>' + "".join(h.td(b, fn(b)) for b in h.order) + "</tr>")

    line("Best search position", lambda b: _pill(f"#{best_rank[b]}", "blue") if b in best_rank else _pill("Not in results", "na"), "visibility")
    line("Mobile performance score", lambda b: score(b, "mobile"), "speed")
    line("Desktop performance score", lambda b: score(b, "desktop"), "speed")
    line("Lighthouse SEO score (mobile)", lambda b: score(b, "mobile", "seo"), "speed")
    line("Indexable (robots meta)", lambda b: robots_cell(h.pages[b]), "onpage")
    line("H1 tag", lambda b: (_pill("Missing", "poor") if c["hcounts"][b][1] == 0 else
                             (_pill(f'{c["hcounts"][b][1]} H1s', "ni") if c["hcounts"][b][1] > 1 else _pill("Present", "good"))), "headings")
    line("H2 / H3 headings", lambda b: f'{c["hcounts"][b][2]} / {c["hcounts"][b][3]}', "headings")
    line("Words on page", lambda b: f'{_int(h.pages[b].get("word_count_total")):,}', "onpage")
    line(f"Topics covered in depth (of {ntop})", lambda b: str(topics_covered(c, b)), "topics")
    line("FAQs on page", lambda b: str(len(h.pages[b].get("faqs") or [])), "faqs")
    line("Data tables", lambda b: str(_int(h.pages[b].get("tables_count"))), "onpage")
    h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Measure") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    obs = []
    for b in h.order:
        rb = (h.pages[b].get("robots_meta") or "").lower()
        if "noindex" in rb:
            obs.append(f"<b>{esc(h.name(b))}</b> carries <code>robots: {esc(h.pages[b].get('robots_meta'))}</code>, which excludes it from search indexes.")
    for b in h.order:
        if c["hcounts"][b][1] == 0:
            obs.append(f"<b>{esc(h.name(b))}</b> has no H1 tag"
                       + (f"; its title tag reads “{esc(h.pages[b].get('title'))}”." if h.pages[b].get("title") else "."))
    if best_rank:
        lead = min(best_rank, key=best_rank.get)
        obs.append(f"<b>{esc(h.name(lead))}</b> holds the best position among the compared brands (#{best_rank[lead]}) across the searches tested."
                   + ("" if h.you in best_rank else f" {esc(h.name(h.you))} does not appear in those results."))
    perf = {b: (psi_rec(c, b, "mobile") or {}).get("scores", {}).get("performance") for b in h.order}
    perf = {b: v for b, v in perf.items() if v is not None}
    if perf:
        hi, lo = max(perf, key=perf.get), min(perf, key=perf.get)
        obs.append(f"Mobile performance ranges from {perf[lo]} ({esc(h.name(lo))}) to {perf[hi]} ({esc(h.name(hi))}); "
                   f"{esc(h.name(h.you))} scores {perf.get(h.you, 'n/a')}.")
    cov = {b: topics_covered(c, b) for b in h.order}
    top = max(cov, key=cov.get)
    obs.append(f"Of {ntop} topics found across the pages, {esc(h.name(top))} covers the most in depth ({cov[top]}); "
               f"{esc(h.name(h.you))} covers {cov[h.you]}.")
    fq = {b: len(h.pages[b].get("faqs") or []) for b in h.order}
    fb = max(fq, key=fq.get)
    obs.append(f"{esc(h.name(fb))} answers the most FAQs ({fq[fb]}); {esc(h.name(h.you))} answers {fq[h.you]}.")
    h.A("<h3>Key observations</h3><ul class=obs>" + "".join(f"<li>{o}</li>" for o in obs) + "</ul>")
    h.end()


def robots_cell(p):
    rb = (p.get("robots_meta") or "").strip()
    if "noindex" in rb.lower():
        return _pill("No (noindex)", "poor")
    if rb or "robots_meta" in p:
        return _pill("Yes", "good")
    return _pill("Yes", "good") if p.get("extraction_status") == "full" else _pill("n/a", "na")


def pages_compared(h):
    h.section("pages", "2", "Pages compared", "The exact pages analysed, as fetched on the collection date.")
    rows = []
    for b in h.order:
        p = h.pages[b]
        rows.append(f'<tr><td class="lab">{h.label(b)}</td><td><a class="mono" href="{esc(p.get("url"))}" target="_blank" rel="noopener">{esc(p.get("url"))}</a></td>'
                    f'<td>{esc(p.get("title"))}</td><td>{esc(p.get("h1") or "—")}</td>'
                    f'<td class="num">{_int(p.get("word_count_total")):,}</td><td class="c">{_pill(p.get("extraction_status") or "full", "blue")}</td></tr>')
    h.A('<div class="tw"><table><thead><tr><th>Brand</th><th>URL</th><th>Title tag</th><th>H1</th><th class="c">Words</th><th class="c">Extraction</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>")
    notes = h.meta.get("notes") or []
    if notes:
        h.A("<h4>Notes on the pages analysed</h4><ul class=plain>" + "".join(f"<li>{esc(n)}</li>" for n in notes) + "</ul>")
    h.end()


def visibility(h):
    c = h.c
    qs = serp_queries(c)
    doms = brand_domains(c)
    h.section("visibility", "3", "Search visibility",
              "Best organic position of any URL on each brand's domain, per search. The page type of the ranking URL is shown in brackets.")
    if not qs:
        h.A('<p class="nc">No search-ranking data was collected for this run.</p>')
        return h.end()
    buyer = [(q, r) for q, r in qs if not any(d in (q or "").lower() for d in doms.get(h.you, ()))]
    rows = []
    for q, res in buyer:
        cells = []
        for b in h.order:
            hit = next((r for r in sorted(res, key=lambda r: r.get("rank") or 99)
                        if any((r.get("domain") or _host(r.get("url"))).endswith(d) for d in doms.get(b, ()))), None)
            cells.append(h.td(b, _pill(f'#{hit["rank"]}', "blue") + f' <span class="small">({page_kind(hit.get("url"))})</span>'
                              if hit else _pill("Not in results", "na")))
        rows.append(f'<tr><td class="lab">{esc(q)}</td>' + "".join(cells) + "</tr>")
    h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Search query") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    depth = max((len(r) for _, r in qs), default=0)
    h.A(f'<p class="small">Top {depth} organic results recorded per search. Positions come from the search index used during collection and vary by location and date.</p>')
    h.A('<details class="topic"><summary><b>Full results for every search</b></summary><div style="padding:12px 16px">')
    for q, res in qs:
        h.A(f"<h4>{esc(q)}</h4><div class=tw><table><thead><tr><th class=c>#</th><th>Domain</th><th>URL</th></tr></thead><tbody>")
        for r in sorted(res, key=lambda r: r.get("rank") or 99):
            owner = next((b for b in h.order if any((r.get("domain") or _host(r.get("url"))).endswith(d) for d in doms.get(b, ()))), None)
            h.A(f'<tr><td class=c>{esc(r.get("rank"))}</td><td>{esc(r.get("domain") or _host(r.get("url")))}'
                + (f' <span class="pill blue">{esc(h.name(owner))}</span>' if owner else "")
                + f'</td><td class=mono>{esc(r.get("url"))}</td></tr>')
        h.A("</tbody></table></div>")
    h.A("</div></details>")
    h.end()


def speed(h):
    c = h.c
    psi = c.get("psi") or {}
    h.section("speed", "4", "Page speed & scores",
              "Lighthouse category scores (0–100) and lab Core Web Vitals for mobile and desktop. "
              "Colour bands follow Google's thresholds: good, needs improvement, poor.")
    if not c.get("psi_by"):
        h.A('<p class="nc">Page-speed data was not collected for this run.</p>')
        return h.end()
    for dev in ("mobile", "desktop"):
        h.A(f"<h3>{dev.title()}: Lighthouse scores</h3>")
        rows = []
        for key, lab in CATS:
            cells = []
            for b in h.order:
                v = ((psi_rec(c, b, dev) or {}).get("scores") or {}).get(key)
                cells.append(h.td(b, _pill(v, rate("score", v)) if v is not None else _pill("n/a", "na")))
            rows.append(f'<tr><td class="lab">{lab}</td>' + "".join(cells) + "</tr>")
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Category") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
        h.A(f"<h3>{dev.title()}: lab metrics</h3>")
        rows = []
        for key, short, long_ in LAB:
            cells = []
            for b in h.order:
                v = ((psi_rec(c, b, dev) or {}).get("lab") or {}).get(key)
                st = rate(key, v) if key not in ("bytes",) else ""
                cells.append(h.td(b, (_pill(_metric(key, v), st) if st else esc(_metric(key, v)))))
            rows.append(f'<tr><td class="lab">{esc(short)}<div class="small" style="font-weight:400">{esc(long_)}</div></td>' + "".join(cells) + "</tr>")
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Metric") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
        field = {b: ((psi_rec(c, b, dev) or {}).get("field") or {}) for b in h.order}
        if any(f.get("has_data") for f in field.values()):
            rows = []
            for key, lab in (("lcp_ms", "LCP (p75)"), ("inp_ms", "INP (p75)"), ("cls", "CLS (p75)"), ("ttfb_ms", "TTFB (p75)")):
                cells = []
                for b in h.order:
                    v = field[b].get(key) if field[b].get("has_data") else None
                    cells.append(h.td(b, _pill(_metric(key, v), rate(key, v)) if v is not None else _pill("No data", "na")))
                rows.append(f'<tr><td class="lab">{lab}</td>' + "".join(cells) + "</tr>")
            h.A(f"<h4>{dev.title()}: real-user field data (Chrome UX Report, 28 days)</h4>"
                '<div class="tw"><table class="cmp"><thead><tr>' + h.th("Metric") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    versions = sorted({(psi_rec(c, b, d) or {}).get("lighthouse_version") for b in h.order for d in ("mobile", "desktop")} - {None, ""})
    when = (psi.get("fetched_at") or "")[:10]
    src = psi.get("source") or "PageSpeed Insights"
    note = f"Source: {esc(src)}" + (f", Lighthouse {esc(', '.join(versions))}" if versions and not any(v in src for v in versions) else "") + (f", measured {esc(when)}" if when else "") + "."
    if "lighthouse" in (psi.get("engines") or []):
        note += (" Lab values come from a single run per page and device and can vary between runs. "
                 "Real-user field data (Chrome UX Report) is only available through the PageSpeed Insights API.")
    h.A(f'<p class="small">{note}</p>')
    h.end()


def links_cell(page, quality):
    n, raw = internal_link_count(page, quality), len(onpage_internal_links(page))
    return str(n) + (f'<div class="small">{raw} including link lists and hubs</div>' if raw != n else "")


def onpage(h):
    c = h.c
    h.section("onpage", "5", "On-page SEO", "The elements search engines read first, exactly as each page ships them.")
    P = h.pages

    def txt(v, n=None):
        v = (v or "").strip()
        if not v:
            return _pill("None", "na")
        return esc(v) + (f'<div class="small">{len(v)} characters</div>' if n else "")

    rows = [
        ("Title tag", lambda b: txt(P[b].get("title"), True)),
        ("Meta description", lambda b: txt(P[b].get("meta_description"), True)),
        ("H1", lambda b: txt(P[b].get("h1")) if P[b].get("h1") else _pill("No H1", "poor")),
        ("Robots meta", lambda b: esc(P[b].get("robots_meta")) if P[b].get("robots_meta") else '<span class="small">Not set (indexable by default)</span>'),
        ("Canonical", lambda b: f'<span class="mono">{esc(P[b].get("canonical"))}</span>' if P[b].get("canonical") else '<span class="small">Not recorded</span>'),
        ("Structured data (JSON-LD)", lambda b: ", ".join(esc(s) for s in P[b].get("schema_types") or []) or _pill("None found", "na")),
        ("Words on page", lambda b: f'{_int(P[b].get("word_count_total")):,}'),
        ("Data tables", lambda b: str(_int(P[b].get("tables_count")))),
        ("Images with alt text", lambda b: f'{_int(P[b].get("image_alt_count"))} of {_int(P[b].get("image_count"))}'),
        ("Internal links in the article", lambda b: links_cell(P[b], c.get("quality") or {})),
        ("External links", lambda b: str(_int(P[b].get("external_link_count")))),
        ("Author", lambda b: esc(P[b].get("author")) if P[b].get("author") else _pill("Not named", "na")),
        ("Reviewer", lambda b: esc(P[b].get("reviewer")) if P[b].get("reviewer") else _pill("Not named", "na")),
        ("Published / updated date on page", lambda b: esc(" / ".join(x for x in (P[b].get("published_date"), P[b].get("modified_date")) if x)) or _pill("Not shown", "na")),
    ]
    body = "".join(f'<tr><td class="lab">{esc(l)}</td>' + "".join(h.td(b, fn(b), "") for b in h.order) + "</tr>" for l, fn in rows)
    h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Element") + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    topic = c["topic"]
    if topic:
        kc = {b: keyword_checks(P[b], topic) for b in h.order}
        yn = lambda v: _pill("Yes", "good") if v else _pill("No", "na")
        krows = [("In title tag", lambda b: yn(kc[b]["title"])), ("In meta description", lambda b: yn(kc[b]["meta"])),
                 ("In H1", lambda b: yn(kc[b]["h1"])), ("In URL", lambda b: yn(kc[b]["url"])),
                 ("In first 100 words", lambda b: yn(kc[b]["first100"])),
                 ("H2/H3 headings containing it", lambda b: f'{kc[b]["subheads"]} of {kc[b]["subheads_total"]}'),
                 ("Exact phrase in body", lambda b: f'{kc[b]["exact_body"]} ({kc[b]["per_1000"]} per 1,000 words)')]
        h.A(f'<h3>Placement of the phrase “{esc(topic)}”</h3><p class="small">All words of the phrase must appear for a Yes; plurals count.</p>')
        body = "".join(f'<tr><td class="lab">{esc(l)}</td>' + "".join(h.td(b, fn(b)) for b in h.order) + "</tr>" for l, fn in krows)
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Placement") + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    h.end()


def headings(h):
    c = h.c
    h.section("headings", "6", "Heading structure",
              "How each page marks up its headings (H1–H4): counts, the H1 itself, and the H1/H2 outline side by side.")
    hc = c["hcounts"]
    rows = []
    for lvl in (1, 2, 3, 4):
        cells = []
        for b in h.order:
            n = hc[b][lvl]
            cells.append(h.td(b, (_pill("Missing", "poor") if lvl == 1 and n == 0 else
                                  _pill(f"{n} (multiple)", "ni") if lvl == 1 and n > 1 else str(n))))
        rows.append(f'<tr><td class="lab">H{lvl}</td>' + "".join(cells) + "</tr>")
    h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Tag") + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    h.A("<h3>H1 and H2 outline, side by side</h3><p class=small>H3 and H4 headings are listed in each page's detail view.</p><div class=grid5>")
    for b in h.order:
        outline = [x for x in h.pages[b].get("heading_outline") or [] if _int(x.get("level")) in (1, 2)]
        items = "".join(f'<li><span class="tag h{_int(x["level"])}">H{_int(x["level"])}</span><span>{esc(x.get("text"))}</span></li>' for x in outline)
        if not any(_int(x.get("level")) == 1 for x in outline):
            items = '<li><span class="pill poor">No H1</span></li>' + items
        h.A(f'<div class="col{" us" if b == h.you else ""}"><h4>{h.label(b)}</h4><ul class="ol">{items or "<li class=nc>No H1/H2 headings</li>"}</ul></div>')
    h.A("</div>")
    tree = c.get("tree") or []
    shared = [r for r in tree if sum(r["present"].values()) >= 2]
    h.A(f'<h3>Headings used by more than one page</h3><p class="small">{len(shared)} of {len(tree)} distinct headings appear on two or more pages (matched ignoring case and punctuation).</p>')
    if shared:
        body = "".join(f'<tr><td><span class="tag h{r["level"]}">H{r["level"]}</span> {esc(r["text"])}</td>'
                       + "".join(h.td(b, _pill("Yes", "good") if r["present"][b] else '<span class="d0">—</span>') for b in h.order) + "</tr>" for r in shared)
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Heading") + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    h.end()


def topic_cov(h):
    c = h.c
    topics = c["topics"]
    h.section("topics", "7", "Topic coverage",
              f"{len(topics)} topics were identified across the five pages. Each cell shows how deeply that page covers the topic: "
              "Deep (a full section with an example, table or calculator), Standard (a proper section), Mention (a line or two), or — (not covered).")
    h.A('<div class="cards">')
    for b in h.order:
        h.A(f'<div class="card{" us" if b == h.you else ""}"><div class="v">{topics_covered(c, b)}</div>'
            f'<div class="l">{h.label(b)}<br>topics covered in depth · {topics_covered(c, b, 1)} mentioned at all</div></div>')
    h.A("</div>")
    for intent in ("high", "medium", "low"):
        rows = [t for t in topics if (t.get("intent") or "medium") == intent]
        if not rows:
            continue
        rows.sort(key=lambda t: -sum(1 for b in h.order if _int(t["brands"][b]["info"].get("depth")) >= 2))
        h.A(f"<h3>{INTENT[intent]} ({len(rows)})</h3>")
        body = []
        for t in rows:
            cells = []
            for b in h.order:
                d = _int(t["brands"][b]["info"].get("depth"))
                lab, cls = DEPTH.get(d, DEPTH[0])
                cells.append(f'<td class="c {cls}">{lab}</td>')
            n = sum(1 for b in h.order if _int(t["brands"][b]["info"].get("depth")) >= 2)
            body.append(f'<tr><td><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a></td>' + "".join(cells) + f'<td class="c">{n}</td></tr>')
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Topic") + '<th class="c xtra">Pages in depth</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>")
    comps = [b for b in h.order if b != h.you]
    missing = [t for t in topics if _int(t["brands"][h.you]["info"].get("depth")) < 2
               and sum(1 for b in comps if _int(t["brands"][b]["info"].get("depth")) >= 2) >= 2]
    only_us = [t for t in topics if _int(t["brands"][h.you]["info"].get("depth")) >= 2
               and not any(_int(t["brands"][b]["info"].get("depth")) >= 2 for b in comps)]
    h.A('<div class="cols2">')
    h.A(f'<div class="card"><h4 style="margin-top:0">Covered in depth by two or more competitors, not by {esc(h.name(h.you))} ({len(missing)})</h4><ul class="plain">'
        + "".join(f'<li><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a> <span class="small">— {", ".join(esc(h.name(b)) for b in comps if _int(t["brands"][b]["info"].get("depth")) >= 2)}</span></li>' for t in missing)
        + "</ul></div>")
    h.A(f'<div class="card us"><h4 style="margin-top:0">Covered in depth only by {esc(h.name(h.you))} ({len(only_us)})</h4><ul class="plain">'
        + "".join(f'<li><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a></li>' for t in only_us) + "</ul></div>")
    h.A("</div>")
    h.end()


def content(h):
    c = h.c
    h.section("content", "8", "Content side by side",
              "For every topic, what each page wrote: the heading it sits under, a summary of the coverage, and the page's own text.")
    h.A('<div class="tools" data-grp="tf"><button class="btn on" onclick="filt(this,\'tf\',\'all\')">All topics</button>'
        '<button class="btn" onclick="filt(this,\'tf\',\'high\')">High-value only</button>'
        f'<button class="btn" onclick="filt(this,\'tf\',\'notours\')">Not covered in depth by {esc(h.name(h.you))}</button>'
        '<span style="flex:1"></span><button class="btn" onclick="accAll(\'#ctopics\',true)">Expand all</button>'
        '<button class="btn" onclick="accAll(\'#ctopics\',false)">Collapse all</button></div><div id="ctopics">')
    order_i = {"high": 0, "medium": 1, "low": 2}
    for i, t in enumerate(sorted(c["topics"], key=lambda t: order_i.get(t.get("intent"), 1))):
        tags = [t.get("intent") or "medium"]
        if _int(t["brands"][h.you]["info"].get("depth")) < 2:
            tags.append("notours")
        chips = "".join(f'<span class="chip {DEPTH.get(_int(t["brands"][b]["info"].get("depth")), DEPTH[0])[1]}">{esc(h.name(b))}: '
                        f'{DEPTH.get(_int(t["brands"][b]["info"].get("depth")), DEPTH[0])[0]}</span>' for b in h.order)
        h.A(f'<details class="topic" id="t-{esc(t["id"])}" data-tf="{" ".join(tags)}"{" open" if (h.p or i < 2) else ""}>'
            f'<summary><b>{esc(t["name"])}</b>{chips}</summary>')
        for b in h.order:
            cell = t["brands"][b]
            info = cell["info"]
            d = _int(info.get("depth"))
            sec = cell.get("sec") if _quotable(cell.get("sec")) else None
            who = f'<div class="who"><b>{esc(h.name(b))}</b>' + ('<span class="us-tag">OUR PAGE</span>' if b == h.you else "")
            if not cell["present"] and d == 0:
                h.A(f'<div class="row{" us" if b == h.you else ""}">{who}</div><div class="nc">Not covered on this page.</div></div>')
                continue
            loc = (f'{esc(cell.get("tag") or "")}' + (f' · “{esc(sec.get("heading"))}”' if sec and sec.get("heading") else "")) if (cell.get("tag") and sec) else ""
            meta_bits = [DEPTH.get(d, DEPTH[0])[0]]
            if info.get("word_count"):
                meta_bits.append(f'~{_int(info.get("word_count"))} words')
            if info.get("has_table"):
                meta_bits.append("table")
            if info.get("has_example"):
                meta_bits.append("worked example")
            who += f'<span class="small">{" · ".join(esc(x) for x in meta_bits)}</span>' + (f'<span class="small">{loc}</span>' if loc else "") + "</div>"
            body = (f'<div class="cap">Summary</div><p class="sum">{esc(info.get("snippet") or "")}</p>') if info.get("snippet") else ""
            text = _sec_text(sec)
            if text:
                head, rest = text[:900], text[900:]
                if rest:
                    cut = head.rfind(" ")
                    head, rest = (head[:cut], head[cut:] + rest) if cut > 600 else (head, rest)
                body += f'<div class="cap">On the page</div><blockquote class="quote">{esc(head)}{"…" if rest else ""}</blockquote>'
                if rest:
                    body += f'<details class="more"><summary>Read the full section</summary><blockquote class="quote more">{esc(text)}</blockquote></details>'
            elif sec and sec.get("summary"):
                body += f'<blockquote class="quote">{esc(sec.get("summary"))}</blockquote>'
            h.A(f'<div class="row{" us" if b == h.you else ""}">{who}<div>{body or "<span class=nc>Covered without a separate section.</span>"}</div></div>')
        h.A("</details>")
    h.A("</div>")
    h.end()


def faqs(h):
    c = h.c
    h.section("faqs", "9", "FAQ comparison", "Questions each page answers. Differently worded questions about the same thing are grouped into one row.")
    h.A('<div class="cards">')
    for b in h.order:
        h.A(f'<div class="card{" us" if b == h.you else ""}"><div class="v">{len(h.pages[b].get("faqs") or [])}</div><div class="l">{h.label(b)}<br>FAQs on the page</div></div>')
    h.A("</div>")
    gaps = (c.get("gaps") or {}).get("faq_gaps") or []
    if gaps:
        comps = [b for b in h.order if b != h.you]
        body = "".join(f'<tr><td>{esc(g.get("question"))}</td>' + "".join(h.td(b, _pill("Yes", "good") if b in (g.get("answered_by") or []) else '<span class="d0">—</span>') for b in comps) + "</tr>" for g in gaps)
        h.A(f"<h3>Questions answered by competitors, not on {esc(h.name(h.you))} ({len(gaps)})</h3>"
            '<div class="tw"><table><thead><tr><th>Question</th>' + "".join(f'<th class="c">{esc(h.name(b))}</th>' for b in comps) + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    rows = c.get("faq_rows") or []
    if rows:
        h.A(f'<h3>All questions across the pages ({len(rows)})</h3><div class="tools"><input class="q" placeholder="Search questions…" oninput="search(this,\'faqm\')"></div>')
        body = "".join(f'<tr><td>{esc(r["question"])}</td>' + "".join(h.td(b, _pill("Yes", "good") if r["present"][b] else '<span class="d0">—</span>') for b in h.order) + "</tr>" for r in rows)
        h.A('<div class="tw" style="max-height:620px"><table class="cmp" id="faqm"><thead><tr>' + h.th("Question") + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    h.end()


def claims(h):
    h.section("claims", "10", "Figures & claims", "Prices, ratios, discounts, plan features and riders exactly as each page states them.")
    h.A('<div class="cols2">')
    for b in h.order:
        p = h.pages[b]
        nums, feats = p.get("numbers") or [], p.get("features_or_riders") or []
        h.A(f'<div class="card{" us" if b == h.you else ""}"><h4 style="margin-top:0">{h.label(b)}</h4>'
            + (f'<div class="small" style="font-weight:600">Figures stated ({len(nums)})</div><ul class="plain">' + "".join(f"<li>{esc(x)}</li>" for x in nums) + "</ul>" if nums else "")
            + (f'<div class="small" style="font-weight:600;margin-top:10px">Plans, features &amp; riders ({len(feats)})</div><ul class="plain">' + "".join(f"<li>{esc(x)}</li>" for x in feats) + "</ul>" if feats else "")
            + "</div>")
    h.A("</div>")
    h.end()


def page_detail(h, b, idx):
    c, p = h.c, h.pages[b]
    hc = c["hcounts"][b]
    h.A(f'<section id="{h.pid(b)}"><h2><span class="n">P{idx}</span>{esc(h.name(b))}'
        + ('<span class="us-tag">OUR PAGE</span>' if b == h.you else "") + "</h2>")
    h.A(f'<p class="lede"><a class="mono" href="{esc(p.get("url"))}" target="_blank" rel="noopener">{esc(p.get("url"))}</a></p>')
    m, d = psi_rec(c, b, "mobile"), psi_rec(c, b, "desktop")
    sc = lambda r, k: (_pill((r.get("scores") or {}).get(k), rate("score", (r.get("scores") or {}).get(k))) if r and (r.get("scores") or {}).get(k) is not None else _pill("n/a", "na"))
    kv = [("Title tag", esc(p.get("title")) or "—"), ("Meta description", esc(p.get("meta_description")) or "—"),
          ("H1", esc(p.get("h1")) if p.get("h1") else _pill("No H1", "poor")),
          ("Headings", f"H1 {hc[1]} · H2 {hc[2]} · H3 {hc[3]} · H4 {hc[4]}"),
          ("Words · tables · FAQs", f'{_int(p.get("word_count_total")):,} words · {_int(p.get("tables_count"))} tables · {len(p.get("faqs") or [])} FAQs'),
          ("Lighthouse (mobile)", " ".join(f'{lab} {sc(m, k)}' for k, lab in CATS)),
          ("Lighthouse (desktop)", " ".join(f'{lab} {sc(d, k)}' for k, lab in CATS)),
          ("Structured data", ", ".join(esc(s) for s in p.get("schema_types") or []) or "None found"),
          ("Robots meta", esc(p.get("robots_meta")) or "Not set"),
          ("Author / reviewer", esc(" / ".join(x for x in (p.get("author"), p.get("reviewer")) if x)) or "Not named")]
    h.A('<div class="kv">' + "".join(f"<div>{esc(k)}</div><div>{v}</div>" for k, v in kv) + "</div>")
    outline = p.get("heading_outline") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Heading outline ({len(outline)} headings)</b></summary><div style="padding:12px 16px"><ul class="ol">'
        + "".join(f'<li class="l{_int(x.get("level"))}"><span class="tag h{_int(x.get("level"))}">H{_int(x.get("level"))}</span><span>{esc(x.get("text"))}</span></li>' for x in outline)
        + "</ul></div></details>")
    secs = [s for s in p.get("sections") or [] if _sec_text(s) or s.get("summary")]
    h.A(f'<details class="topic" open><summary><b>Page content by section ({len(secs)} sections)</b></summary><div style="padding:14px 18px">')
    for s in secs:
        lvl = _int(s.get("level"))
        tag = f'<span class="tag h{lvl}">H{lvl}</span>' if lvl else '<span class="tag">Intro</span>'
        text = _sec_text(s)
        body = esc(text) if text else f'<span class="nc">{esc(s.get("summary"))}</span>'
        h.A(f'<div class="sec"><h5>{tag}<span>{esc(s.get("heading") or "(introduction)")}</span></h5><p>{body}</p></div>')
    h.A("</div></details>")
    fq = p.get("faqs") or []
    if fq:
        h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>FAQs ({len(fq)})</b></summary><div style="padding:12px 16px">')
        cats = {}
        for f in fq:
            cats.setdefault(f.get("category") or "", []).append(f)
        for cat, items in cats.items():
            if cat:
                h.A(f"<h4>{esc(cat)} ({len(items)})</h4>")
            for f in items:
                h.A(f'<details class="faq"{" open" if h.p else ""}><summary>{esc(f.get("question"))}</summary><div>{esc(f.get("answer"))}</div></details>')
        h.A("</div></details>")
    ex = p.get("examples") or []
    if ex:
        h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Worked examples and illustrations ({len(ex)})</b></summary><div style="padding:12px 16px">'
            '<div class="tw"><table><thead><tr><th>Context</th><th>Figures</th></tr></thead><tbody>'
            + "".join(f'<tr><td>{esc(e.get("context"))}</td><td>{esc(e.get("figures"))}</td></tr>' for e in ex) + "</tbody></table></div></div></details>")
    links = onpage_internal_links(p)
    ext = p.get("external_links") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Links ({len(links)} internal in content · {len(ext)} external)</b></summary><div style="padding:12px 16px">'
        '<div class="tw" style="max-height:480px"><table><thead><tr><th>Anchor text</th><th>Target</th><th>Section</th><th>Type</th></tr></thead><tbody>'
        + "".join(f'<tr><td>{esc(l.get("anchor") or "(no text)")}</td><td class="mono">{esc(l.get("href"))}</td><td>{esc(l.get("section"))}</td>'
                  f'<td>{"Internal" if l.get("internal") else "External"}</td></tr>' for l in links + ext)
        + "</tbody></table></div></div></details>")
    imgs = p.get("images") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Images ({len(imgs)}, {sum(1 for i in imgs if i.get("alt"))} with alt text)</b></summary><div style="padding:12px 16px">'
        '<div class="tw" style="max-height:420px"><table><thead><tr><th>Alt text</th><th>Source</th></tr></thead><tbody>'
        + "".join(f'<tr><td>{esc(i.get("alt")) or _pill("No alt", "na")}</td><td class="mono">{esc(i.get("src"))}</td></tr>' for i in imgs)
        + "</tbody></table></div></div></details>")
    h.A("</section>")


def method(h):
    c, meta = h.c, h.meta
    psi = c.get("psi") or {}
    h.A('<section id="method"><h2><span class="n">A</span>Method &amp; sources</h2>')
    items = [
        f"Pages: fetched on {esc(meta.get('created_at') or '')}; headings, links, images, tables and structured data parsed from the raw HTML; "
        "each section then read for its meaning, FAQs, examples and figures.",
        "Topics: sections from all pages grouped into shared topics; each page scored per topic as Deep, Standard, Mention or not covered.",
        "FAQs: questions grouped across pages when they ask the same thing in different words.",
        "Search visibility: organic results recorded for each search query; positions vary by location, device and date.",
        f"Page speed: {esc(psi.get('source') or 'not collected')}.",
    ]
    if not c.get("auth"):
        items.append("Authority metrics (backlinks, domain rating) are not included: no Ahrefs data was collected for this run.")
    h.A("<ul class=plain>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
    h.A(f'<p class="foot">Generated {datetime.now().strftime("%d %b %Y, %H:%M")} · run folder: {esc(c.get("run_name"))}</p></section>')


# ----------------------------------------------------------------------------- entry
def render(ctx, print_mode=False):
    h = R(ctx, print_mode)
    title = f'{(ctx["topic"] or "Content").title()} — Competitive Content Comparison'
    h.A(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}</title><style>{CSS}</style></head><body>')
    nav(h)
    h.A("<main>")
    header(h)
    for fn in (summary, pages_compared, visibility, speed, onpage, headings, topic_cov, content, faqs, claims):
        fn(h)
    for i, b in enumerate(h.order, 1):
        page_detail(h, b, i)
    method(h)
    h.A(f"</main><script>{JS}</script></body></html>")
    return "".join(h.out)
