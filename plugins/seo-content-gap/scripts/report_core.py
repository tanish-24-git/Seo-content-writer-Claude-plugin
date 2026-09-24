"""Shared data layer for the content-gap report: loading a run, brand-key
resolution, heading / topic / FAQ coverage, content helpers, and the inputs from
PageSpeed Insights (pagespeed.json) and Ahrefs (authority.json).

Standard library only. Used by build_report.py and the report_* renderers.
"""
import difflib
import html
import json
import os
import re
import sys
from urllib.parse import quote


# ----------------------------- load -----------------------------------------
def _load(path, default):
    try:
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
        if name.endswith(".json") and not name.endswith(".bak.json") and (name == "our.json" or name.startswith("competitor")):
            pages.append(_load(os.path.join(run_dir, name), {}))
    return meta, clusters, gaps, pages


def brand_order(meta, gaps, pages):
    your = gaps.get("your_brand") or meta.get("your_brand") or "OUR PAGE"
    order = [your]
    for p in pages:
        b = p.get("brand")
        if b and b not in order:
            order.append(b)
    return your, order


def esc(x):
    return html.escape(str(x if x is not None else ""))


# Strip form-widget noise that leaks into extracted section text — long runs of
# phone country codes (e.g. "+91 +1 (USA) +1 (CAN) +61 (AUS) +65 +962 ...") from
# the phone-number dropdown on premium-calculator forms. 4+ consecutive "+code"
# tokens is a country picker, never prose.
_PHONE_CODE_RUN = re.compile(r'(?:\+\d{1,4}(?:\s*\([^)]{1,8}\))?\s*){4,}')
# Income-band picker runs, e.g. "< 2.5 Lakhs 2.5 - 5 Lakhs 5 - 7.5 Lakhs ...".
_INCOME_BAND_RUN = re.compile(
    r'(?:[<>]?\s*\d[\d.,]*\s*(?:-\s*\d[\d.,]*)?\s*Lakhs?\b[\s,]*){2,}', re.I)


# Lead-form / consent / feedback-widget boilerplate that extraction captures as
# section text: consent checkboxes, call-back authorisations, "was this helpful"
# Yes/No surveys, review forms, and stray widget markers (~~ ^^^ ## ** $$).
_WIDGET_JUNK = [re.compile(p, re.I | re.S) for p in (
    r"I agree and consent to the Terms\s*&\s*Conditions(?:,| and the)? Privacy Policy",
    r"Please agree to Terms and Conditions",
    r"I hereby authori[sz]e .{0,900}? business",
    r"Please refer to .{0,60}? Privacy Policy",
    r"Customer Reviews Customer Rating Reviews by customers",
    r"Rate & Review \(Rate your experience on the website\)",
    r"Please select the rating to proceed",
    r"Tell us how was your experience \?",
    r"(?:\b\d\.\s[^.?]{3,80}?\??\s+Yes\s+No\b\s*)+(?:\d\.\s*)?",
    r"Write Your Review \d+ characters remaining",
    r"Thank You\. Your review has been submitted successfully\. Go Back",
    r"Need Assistance\?",
    r"(?:Have )?Us Call You Select Plan Type(?: Buy Now)?",
    r"[×X]\s*Terms & Conditions\s*(?:I\b)?",
    r"(?:[~^#*$|]{2,}\s*)+",
)]


def clean_text(t):
    if not t:
        return t
    t = _PHONE_CODE_RUN.sub(" ", t)
    t = _INCOME_BAND_RUN.sub(" ", t)
    for rx in _WIDGET_JUNK:
        t = rx.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def page_by_brand(pages):
    return {p.get("brand"): p for p in pages}


# --------------------- resilient brand-key resolution -----------------------
# clusters.json / gaps.json are written by the gap-analyst agent and SHOULD key
# every brand map under the exact canonical brand string from meta.json. If the
# agent drifts (short form, "OUR PAGE", the URL), an exact lookup silently zeroes
# the column. Resolve case/whitespace-insensitively, and never fail silently.
def _norm(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "").strip().lower())


def resolve_brand_key(brand_map, canonical):
    """Return the key in brand_map matching `canonical` — exact first, then
    case/whitespace-insensitive. None if nothing matches."""
    if not isinstance(brand_map, dict) or not brand_map:
        return None
    if canonical in brand_map:
        return canonical
    target = _norm(canonical)
    for k in brand_map:
        if _norm(k) == target:
            return k
    return None


def map_get(brand_map, canonical, default=None):
    """brand_map value for the canonical brand via resilient resolution."""
    key = resolve_brand_key(brand_map or {}, canonical)
    return (brand_map or {}).get(key, default) if key is not None else default


def brand_entry(brand_map, canonical):
    """The dict entry for a canonical brand, or {} — for cluster brand maps."""
    return map_get(brand_map, canonical, {}) or {}


# Internal links inside nav / header / footer are site-wide boilerplate, not
# on-page editorial links. Exclude them everywhere (counts, charts, tables, gap
# analysis) so internal-link comparisons reflect real in-content linking only.
NAV_FOOTER_SCOPES = {"nav", "header", "footer"}


def onpage_internal_links(page):
    """A page's internal links with nav/header/footer boilerplate stripped out."""
    return [l for l in (page.get("internal_links") or [])
            if (l.get("scope") or "in-content") not in NAV_FOOTER_SCOPES]


def covers(info):
    """True if a brand actually addresses a cluster (present flag or depth > 0)."""
    return bool(info.get("present")) or int(info.get("depth", 0) or 0) > 0


def unique_clusters_by_brand(clusters, order):
    """Map brand -> [cluster names] that ONLY that brand covers — the unique
    content angle no other compared page has."""
    out = {b: [] for b in order}
    for c in clusters.get("clusters", []):
        owners = [b for b in order if covers(brand_entry(c.get("brands"), b))]
        if len(owners) == 1:
            out[owners[0]].append(c.get("name"))
    return out


def _normh(t):
    """Normalise a heading for cross-company matching (case/punctuation-blind)."""
    t = re.sub(r"[^\w\s]", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def heading_coverage(pages, order):
    """Every H1/H2/H3 heading across all pages, as a NESTED tree in document
    order: each H1 is followed by its child H2s, each H2 by its child H3s
    (the 'Term Category Page' hierarchy view). Headings are matched
    case/punctuation-insensitively within a level. The tree is anchored to the
    first page (your page) and competitor-unique branches are appended where
    they nest. Returns rows in depth-first order: [{level, text, present:{brand:bool}}].
    """
    pbb = page_by_brand(pages)
    nodes = {}   # (level, norm) -> node
    root = []    # top-level H1 nodes, in first-seen order

    def node(level, nk, text):
        k = (level, nk)
        n = nodes.get(k)
        if n is None:
            n = {"level": level, "text": text, "present": set(),
                 "children": [], "attached": False}
            nodes[k] = n
        return n

    for b in order:
        p = pbb.get(b) or {}
        cur1 = cur2 = None  # keys of the current H1 / H2 while walking this page
        for h in (p.get("heading_outline") or []):
            lvl = int(h.get("level", 0) or 0)
            if lvl not in (1, 2, 3):
                continue
            t = (h.get("text") or "").strip()
            if not t:
                continue
            nk = _normh(t)
            n = node(lvl, nk, t)
            n["present"].add(b)
            if not n["attached"]:
                n["attached"] = True
                parent = None
                if lvl == 2:
                    parent = cur1
                elif lvl == 3:
                    parent = cur2 or cur1
                if parent is not None and parent in nodes:
                    nodes[parent]["children"].append(n)
                else:
                    root.append(n)
            if lvl == 1:
                cur1, cur2 = (1, nk), None
            elif lvl == 2:
                cur2 = (2, nk)

    rows = []

    def dfs(n):
        rows.append({"level": n["level"], "text": n["text"],
                     "present": {b: (b in n["present"]) for b in order}})
        for ch in n["children"]:
            dfs(ch)

    for n in root:
        dfs(n)
    return rows


def covered_not_in_headings(page):
    """Pseudo-headings on this page whose text is NOT any real H1/H2/H3 — topics
    the page presents as section titles but ships inside <p>/<div>/<span> (or a
    styled class), so a crawler / AI bot never registers them as headings.
    Returns rows in document order with a suggested heading level."""
    real = set()
    for h in (page.get("heading_outline") or []):
        if int(h.get("level", 0) or 0) in (1, 2, 3):
            real.add(_normh(h.get("text")))
    seen, out = set(), []
    for ph in (page.get("pseudo_headings") or []):
        t = (ph.get("text") or "").strip()
        nk = _normh(t)
        if not nk or nk in real or nk in seen:
            continue
        seen.add(nk)
        pl = int(ph.get("parent_level", 0) or 0)
        out.append({"text": t, "tag": ph.get("tag") or "p",
                    "class": (ph.get("class") or "").split()[0] if ph.get("class") else "",
                    "parent_heading": ph.get("parent_heading") or "",
                    "parent_level": pl, "seq": int(ph.get("seq", 0) or 0),
                    "suggested": "H3" if pl >= 2 else "H2"})
    return out


def content_coverage(clusters, order):
    """Every topic cluster across the pages as a flat Yes/No matrix: does each
    company cover this topic ANYWHERE on the page — in a heading OR in body copy,
    even if it is worded differently? This is the header-blind companion to
    heading_coverage(): that one asks 'is the topic an H-tag?', this asks 'is the
    topic present at all?'. Driven by the gap-analyst's block-to-block clustering,
    which already aligns differently-phrased coverage of the same topic, so a
    topic everyone covers but writes up in their own words still reads as Yes.
    Returns [{topic, present:{brand:bool}}] in cluster order."""
    rows = []
    for c in clusters.get("clusters", []):
        present = {b: covers(brand_entry(c.get("brands"), b)) for b in order}
        rows.append({"topic": c.get("name") or "", "present": present})
    return rows


_FAQ_STOP = set((
    "a an the is are was were do does did of to for in on at with my our your their i you it its "
    "what which how when why who whom whose can could will would should shall may might must need "
    "and or vs versus be been being have has had this that these those if then than as about into "
    "by from get got give vs. e g eg etc"
).split())


def _faq_tokens(q):
    """Content tokens of an FAQ question, stop-words stripped — used to group
    differently-worded questions about the same thing."""
    toks = re.sub(r"[^\w\s]", " ", (q or "").lower()).split()
    return set(t for t in toks if t not in _FAQ_STOP and len(t) > 2)


def faq_coverage(gaps, pages, order, your, topic=""):
    """Every distinct FAQ across the pages as a Yes/No matrix: does each company
    answer this question — even if they phrase it differently? Differently-worded
    questions about the same thing are grouped by content-token overlap so e.g.
    'Is a medical test required?' and 'Do I need a medical test for term
    insurance?' count as one row. Prefers an explicit gaps['faq_coverage'] from
    the gap-analyst (semantic, most accurate); otherwise clusters the raw page
    FAQs deterministically. Returns [{question, present:{brand:bool}}],
    most-covered first. Words from the run's `topic` (and generic product words)
    are ignored when grouping — they appear in nearly every question and would
    otherwise merge unrelated questions."""
    # 1) gap-analyst semantic enrichment, if provided
    enr = gaps.get("faq_coverage")
    if isinstance(enr, list) and enr:
        rows = []
        for e in enr:
            if not isinstance(e, dict):
                continue
            q = e.get("question") or e.get("q") or ""
            pres = e.get("present")
            if isinstance(pres, dict):
                present = {b: bool(map_get(pres, b, False)) for b in order}
            else:
                ab = e.get("answered_by") or []
                present = {b: any(_norm(b) == _norm(x) for x in ab) for b in order}
            if q:
                rows.append({"question": q, "present": present})
        if rows:
            rows.sort(key=lambda r: sum(r["present"].values()), reverse=True)
            return rows
    # 2) deterministic fallback — cluster page FAQs by token overlap
    pbb = page_by_brand(pages)
    groups = []  # [{rep, has_ours, toks, present:set}]
    for b in order:
        p = pbb.get(b) or {}
        for fq in (p.get("faqs") or []):
            q = (fq.get("question") or "").strip()
            tk = _faq_tokens(q)
            tk = (tk - _GENERIC_TOPIC_WORDS - _faq_tokens(topic)) or tk
            if not q or not tk:
                continue
            best, bestj = None, 0.0
            for g in groups:
                inter = len(tk & g["toks"])
                union = len(tk | g["toks"]) or 1
                j = inter / union
                if j > bestj:
                    best, bestj = g, j
            if best is not None and bestj >= 0.5:
                best["present"].add(b)
                best["toks"] |= tk
                # prefer OUR phrasing as the representative, else the shortest
                if (b == your and not best["has_ours"]) or \
                   (best["has_ours"] == (b == your) and len(q) < len(best["rep"])):
                    best["rep"] = q
                if b == your:
                    best["has_ours"] = True
            else:
                groups.append({"rep": q, "has_ours": (b == your),
                               "toks": set(tk), "present": {b}})
    rows = [{"question": g["rep"], "present": {b: (b in g["present"]) for b in order}}
            for g in groups]
    rows.sort(key=lambda r: sum(r["present"].values()), reverse=True)
    return rows


def merged_outline(page):
    """The page's real headings + its not-in-heading topics, interleaved in true
    document order (by seq). Real headings carry their current tag; pseudo rows
    are flagged with the tag they SHOULD become. This is the 'corrected reading
    order' a crawler should see."""
    rows = []
    for h in (page.get("heading_outline") or []):
        lvl = int(h.get("level", 0) or 0)
        if lvl in (1, 2, 3):
            rows.append({"seq": int(h.get("seq", 0) or 0), "kind": "real",
                         "tag": "H%d" % lvl, "level": lvl, "text": h.get("text") or ""})
    for r in covered_not_in_headings(page):
        rows.append({"seq": r["seq"], "kind": "pseudo",
                     "tag": "<%s>" % r["tag"], "level": int(r["suggested"][1]),
                     "text": r["text"], "suggested": r["suggested"]})
    rows.sort(key=lambda x: x["seq"])
    return rows


def structure_problems(page):
    """Deterministic structural problems for a page, from a crawler's view.
    Returns [(area, problem)]. Used as the baseline for the structure-fix section
    (the analyst may add richer, query-aware notes via gaps['structure_fix'])."""
    hc = page.get("heading_counts", {}) or {}
    h1, h2, h3 = hc.get("h1", 0), hc.get("h2", 0), hc.get("h3", 0)
    title = (page.get("title") or "").strip()
    out = []
    if h1 == 0:
        out.append(("H1", "No &lt;h1&gt; on the page — add exactly one H1 naming the primary topic."))
    elif h1 > 1:
        out.append(("H1", f"{h1} &lt;h1&gt; tags — keep exactly one; demote the extra(s) to H2."))
    if not title:
        out.append(("Title", "No &lt;title&gt; tag detected — add a concise, keyword-led title."))
    if h2 and h3 == 0:
        out.append(("Hierarchy", f"Flat outline — {h2} H2s and zero H3s. Sub-topics aren't nested; "
                                  "group detail points under their parent H2 as H3."))
    nh = covered_not_in_headings(page)
    if nh:
        out.append(("Heading markup", f"{len(nh)} topic(s) are styled as titles but use "
                    "&lt;p&gt;/&lt;div&gt;/&lt;span&gt;, not heading tags — invisible to crawlers "
                    "as headings (see promote list below)."))
    return out


def check_brand_keys(clusters, order):
    """Loud per-cluster warnings: a canonical brand that resolves to NO key in a
    cluster that DOES carry brand data — that column would render empty."""
    warnings = []
    for c in clusters.get("clusters", []):
        bmap = c.get("brands") or {}
        if not bmap:
            continue
        for b in order:
            if resolve_brand_key(bmap, b) is None:
                warnings.append(
                    "cluster %r: brand %r has NO matching key in clusters.json "
                    "(keys present: %s) -- its column would be empty."
                    % (c.get("name"), b, sorted(bmap.keys())))
    return warnings


def assert_your_column(clusters, your):
    """Fail loudly if the your-brand column is entirely zero across all clusters
    that carry brand data — almost always a key mismatch, not a real result."""
    cls = clusters.get("clusters", [])
    if not cls or not any((c.get("brands") or {}) for c in cls):
        return
    total = sum(int(brand_entry(c.get("brands"), your).get("depth", 0) or 0) for c in cls)
    if total == 0:
        bar = "=" * 72
        print("\n%s" % bar, file=sys.stderr)
        print("ERROR: the your-brand column (%r) is ZERO across all %d clusters."
              % (your, len(cls)), file=sys.stderr)
        print("This almost always means clusters.json keyed your page under a", file=sys.stderr)
        print("different string than meta.your_brand (e.g. 'OUR PAGE' or the URL)", file=sys.stderr)
        print("-- a key mismatch, not a real 'your page covers nothing' result.", file=sys.stderr)
        print("Fix: make every key in each cluster's 'brands' map exactly match", file=sys.stderr)
        print("meta.your_brand / competitors[].brand. The report was written but", file=sys.stderr)
        print("the your-brand column is INVALID until the keys are corrected.", file=sys.stderr)
        print("%s\n" % bar, file=sys.stderr)
        sys.exit(2)


# --------------------- content helpers (the new value) ----------------------
def best_section(page, cluster_name):
    """Pick the page section whose heading best matches the cluster name."""
    best, score = None, 0.0
    cn = (cluster_name or "").lower()
    for s in page.get("sections", []):
        r = difflib.SequenceMatcher(None, cn, (s.get("heading") or "").lower()).ratio()
        if r > score:
            best, score = s, r
    return best if score >= 0.34 else None


def similarity(a, b):
    a = (a or "")[:2500].lower()
    b = (b or "")[:2500].lower()
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio() * 100)


def sim_verdict(pct):
    if pct >= 80:
        return "near-duplicate"
    if pct >= 55:
        return "same idea, reworded"
    if pct >= 30:
        return "loosely related"
    return "distinct"


def textfrag(url, heading):
    """Deep-link that opens the live page scrolled to this heading (Chrome)."""
    if not url:
        return "#"
    frag = quote((heading or "")[:120])
    return f"{url}#:~:text={frag}" if frag else url


# ------------------------------------------------------------------------------
# v0.7 data layer: PageSpeed + Ahrefs inputs, H1-H4 hierarchy, topic -> heading
# mapping, keyword placement, and one context object the renderers share.
# ------------------------------------------------------------------------------
DEPTH_LABEL = {0: "", 1: "Mention", 2: "Standard", 3: "Deep"}
PRIORITY_LABEL = {3: "High", 2: "Medium", 1: "Low"}

# Google Core Web Vitals / Lighthouse thresholds: (good upper bound, needs-improvement upper bound)
THRESHOLDS = {"lcp_ms": (2500, 4000), "inp_ms": (200, 500), "cls": (0.1, 0.25), "fcp_ms": (1800, 3000),
              "ttfb_ms": (800, 1800), "tbt_ms": (200, 600), "si_ms": (3400, 5800), "score": (90, 50)}
FIELD_CATEGORY = {"FAST": "good", "AVERAGE": "ni", "SLOW": "poor"}


def rate(metric, v):
    """'good' | 'ni' | 'poor' | '' for a metric value against Google's thresholds."""
    if v is None or metric not in THRESHOLDS:
        return ""
    g, n = THRESHOLDS[metric]
    if metric == "score":
        return "good" if v >= g else ("ni" if v >= n else "poor")
    return "good" if v <= g else ("ni" if v <= n else "poor")


def median(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def heading_counts(page):
    c = {1: 0, 2: 0, 3: 0, 4: 0}
    for h in page.get("heading_outline") or []:
        lvl = int(h.get("level") or 0)
        if 1 <= lvl <= 4:
            c[lvl] += 1
    return c


def heading_tree(pages, order, maxlvl=4):
    """Every H1..H4 heading across pages as one nested tree in document order
    (heading_coverage() extended to H4). Rows: [{level, text, present:{brand:bool}}]."""
    pbb = page_by_brand(pages)
    nodes, root = {}, []
    for b in order:
        cur = {}
        for h in (pbb.get(b) or {}).get("heading_outline") or []:
            lvl = int(h.get("level") or 0)
            t = (h.get("text") or "").strip()
            if not (1 <= lvl <= maxlvl) or not t:
                continue
            key = (lvl, _normh(t))
            n = nodes.get(key)
            if n is None:
                n = nodes[key] = {"level": lvl, "text": t, "present": set(), "children": [], "attached": False}
            n["present"].add(b)
            if not n["attached"]:
                n["attached"] = True
                parent = next((cur[l] for l in range(lvl - 1, 0, -1) if cur.get(l)), None)
                (nodes[parent]["children"] if parent in nodes else root).append(n)
            cur[lvl] = key
            for deeper in range(lvl + 1, maxlvl + 1):
                cur[deeper] = None
    rows = []

    def dfs(n):
        rows.append({"level": n["level"], "text": n["text"], "present": {b: b in n["present"] for b in order}})
        for ch in n["children"]:
            dfs(ch)
    for n in root:
        dfs(n)
    return rows


_GENERIC_TOPIC_WORDS = {"term", "insurance", "plan", "plans", "life", "policy", "guide", "best", "online"}
_BOILERPLATE_HEADING = re.compile(
    r"^\(intro\)$|disclaimer|popular searches|footer|related (articles|links)|^videos?$|download|bookmark", re.I)


def _topic_tokens(text, extra_generic=()):
    tk = _faq_tokens(re.sub(r"\(.*?\)", " ", text or ""))
    core = tk - _GENERIC_TOPIC_WORDS - set(extra_generic)
    return core or tk


def match_section(page, topic, snippet="", extra_generic=()):
    """The section that covers `topic` on `page`: a heading that matches the topic
    (never the H1 or boilerplate), confirmed against the analyst's snippet; else
    the section whose text best matches the snippet. Returns (section, tag) where
    tag is 'H2'..'H6' or 'Body' (covered in text, no dedicated heading)."""
    tk, sk = _topic_tokens(topic, extra_generic), _topic_tokens(snippet, extra_generic)
    name = re.sub(r"\(.*?\)", " ", topic or "").lower().strip()
    secs = [s for s in page.get("sections") or []
            if int(s.get("level") or 0) >= 2 and s.get("heading") and not _BOILERPLATE_HEADING.search(s.get("heading") or "")]
    # The analyst's snippet often names the section outright: "H2 'What is X?'" / "(under 'Benefits')".
    for q in re.findall(r"[‘'\"“]([^'\"’”]{3,120})[’'\"”]", snippet or ""):
        hit = next((s for s in secs if _normh(s.get("heading")) == _normh(q)), None)
        if hit:
            return hit, "H%d" % int(hit.get("level") or 0)
    best, best_score = None, 0.0
    for s in secs:
        h = (s.get("heading") or "").lower()
        hs = max(difflib.SequenceMatcher(None, name, h).ratio() - 0.1, len(tk & _topic_tokens(h, extra_generic)) / max(1, len(tk)))
        if hs < 0.5:
            continue
        score = hs + (0.5 * len(sk & _topic_tokens(s.get("text"), extra_generic)) / max(1, len(sk)) if sk else 0)
        if score > best_score:
            best, best_score = s, score
    if best is not None:
        return best, "H%d" % int(best.get("level") or 0)
    best, best_score = None, 0.0
    for s in secs:
        score = len(sk & _topic_tokens(s.get("text"), extra_generic)) / max(1, len(sk)) if sk else 0
        if score > best_score:
            best, best_score = s, score
    return (best if best_score >= 0.4 else None), "Body"


def section_by_heading(page, heading):
    nh = _normh(heading)
    return next((s for s in page.get("sections") or [] if _normh(s.get("heading")) == nh), None)


def topic_rows(clusters, pages, order, topic=""):
    """Per cluster and brand: coverage info, the covering section and its heading tag.
    Prefers the analyst's recorded `heading` / `heading_level`; falls back to matching."""
    pbb = page_by_brand(pages)
    generic = _faq_tokens(topic)
    out = []
    for c in clusters.get("clusters", []):
        row = {"id": c.get("id"), "name": c.get("name") or "", "intent": c.get("intent") or "", "brands": {}}
        for b in order:
            info = brand_entry(c.get("brands"), b)
            present = covers(info)
            sec, tag, source = None, "", ""
            if present:
                page = pbb.get(b) or {}
                if info.get("heading"):
                    sec = section_by_heading(page, info["heading"]) or {"heading": info["heading"], "text": ""}
                    lvl = info.get("heading_level") or sec.get("level")
                    tag, source = ("H%d" % int(lvl) if lvl else "Body"), "analyst"
                elif info.get("heading_level") == 0:
                    tag, source = "Body", "analyst"
                    sec, _ = match_section(page, c.get("name"), info.get("snippet") or "", generic)
                else:
                    sec, tag = match_section(page, c.get("name"), info.get("snippet") or "", generic)
                    source = "matched"
            row["brands"][b] = {"info": info, "present": present, "sec": sec, "tag": tag, "source": source}
        out.append(row)
    return out


# --- keyword placement --------------------------------------------------------
_IRREGULAR = {"woman": "women", "man": "men", "child": "children"}


def _stem(w):
    w = _IRREGULAR.get(w, w)
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _word_set(text):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower())}


def topic_terms(topic):
    stop = {"for", "the", "a", "an", "of", "in", "on", "to", "and", "with", "vs"}
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", (topic or "").lower()) if w not in stop]


def has_all_terms(text, terms):
    ws = _word_set(text)
    return bool(terms) and all(t in ws for t in terms)


def phrase_regex(topic):
    words = re.findall(r"[a-z0-9]+", (topic or "").lower())
    if not words:
        return None
    return re.compile(r"\b" + r"\s+".join(re.escape(w) + r"s?" for w in words) + r"\b", re.I)


def page_body(page):
    return " ".join(clean_text(s.get("text") or "") for s in page.get("sections") or [])


def keyword_checks(page, topic):
    """Placement of the target topic phrase in the elements search engines weigh."""
    terms, rx = topic_terms(topic), phrase_regex(topic)
    body = page_body(page)
    words = max(1, len(body.split()))
    hs = [h for h in page.get("heading_outline") or [] if int(h.get("level") or 0) in (2, 3)]
    n = len(rx.findall(body)) if rx else 0
    return {
        "title": has_all_terms(page.get("title"), terms),
        "meta": has_all_terms(page.get("meta_description"), terms),
        "h1": has_all_terms(page.get("h1"), terms),
        "url": has_all_terms(re.sub(r"[-_/.]", " ", page.get("url") or ""), terms),
        "first100": has_all_terms(" ".join(body.split()[:100]), terms),
        "subheads": sum(has_all_terms(h.get("text"), terms) for h in hs),
        "subheads_total": len(hs),
        "exact_body": n,
        "per_1000": round(n / words * 1000, 1),
    }


# --- misc ---------------------------------------------------------------------
def internal_link_count(page, quality):
    """In-article internal links: the analyst's count when given (it can exclude
    mega-menus the HTML parser cannot), else nav/header/footer-stripped links."""
    q = map_get(quality, page.get("brand"), {}) or {}
    v = q.get("internal_links")
    return v if isinstance(v, int) else len(onpage_internal_links(page))


def serp_matrix(ranking):
    best = {}
    for r in ranking.get("ranking_pages") or []:
        k = (r.get("query"), r.get("domain") or r.get("brand"))
        if r.get("rank") and (k not in best or r["rank"] < best[k]):
            best[k] = r["rank"]
    return ranking.get("queries_used") or [], best


def by_brand(doc, order):
    """{brand: record} from a pagespeed.json / authority.json 'pages' list (resilient keys)."""
    recs = {p.get("brand"): p for p in (doc or {}).get("pages") or []}
    return {b: map_get(recs, b) for b in order if map_get(recs, b) is not None}


def build_context(run_dir):
    """Everything the HTML / XLSX / PDF renderers need, computed once."""
    meta, clusters, gaps, pages = load_run(run_dir)
    pages = [p for p in pages if p.get("brand")]
    your = gaps.get("your_brand") or meta.get("your_brand") or "OUR PAGE"
    pbb = page_by_brand(pages)
    order = [your] + [c.get("brand") for c in meta.get("competitors") or [] if c.get("brand") and c.get("brand") != your]
    order = [b for b in order if b in pbb] + [p.get("brand") for p in pages if p.get("brand") not in order]
    for p in pages:
        for s in p.get("sections") or []:
            s["text"] = clean_text(s.get("text"))
    topic = meta.get("topic") or gaps.get("topic") or ""
    quality = (gaps.get("quality") or {}).get("per_brand") or {}
    psi = _load(os.path.join(run_dir, "pagespeed.json"), None)
    auth = _load(os.path.join(run_dir, "authority.json"), None)
    ranking = _load(os.path.join(run_dir, "ranking.json"), None) or _load(os.path.join(run_dir, "ranking-result.json"), {}) or {}
    return {
        "run_dir": run_dir, "run_name": os.path.basename(os.path.abspath(run_dir)),
        "meta": meta, "clusters": clusters, "gaps": gaps, "pages": pbb, "page_list": pages,
        "your": your, "order": order, "topic": topic,
        "kpis": gaps.get("kpis") or {}, "quality": quality, "ranking": ranking,
        "psi": psi, "psi_by": by_brand(psi, order) if psi else {},
        "auth": auth, "auth_by": by_brand(auth, order) if auth else {},
        "topics": topic_rows(clusters, pages, order, topic),
        "tree": heading_tree(pages, order),
        "faq_rows": faq_coverage(gaps, pages, order, your, topic),
        "hcounts": {b: heading_counts(pbb[b]) for b in order},
        "gap_list": sorted(gaps.get("gaps") or [], key=lambda g: -int(g.get("priority") or 0)),
        "unique": unique_clusters_by_brand(clusters, order),
        "not_in_headings": {b: covered_not_in_headings(pbb[b]) for b in order},
        "structure_problems": structure_problems(pbb[your]) if your in pbb else [],
    }
