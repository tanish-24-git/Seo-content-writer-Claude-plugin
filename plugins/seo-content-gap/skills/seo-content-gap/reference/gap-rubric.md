# Gap rubric — how to score alignment, clusters, and gaps

## Depth scale (per brand, per cluster)
- **0 — absent:** the brand does not cover this topic.
- **1 — mention:** a sentence or passing reference.
- **2 — standard:** a proper section with explanation.
- **3 — deep:** a proper section **plus** a worked example, a table, or a calculator/illustration.

## Gap types
| Type | Trigger | Writer action |
|---|---|---|
| **missing** | ≥2 competitors cover the cluster at depth ≥2, OUR depth = 0 | ADD a section |
| **thin** | OUR depth < competitor **median** depth (or no example/table where they have one) | EXPAND |
| **unique** | only OUR page covers the cluster at depth ≥2 | KEEP / promote as a differentiator |
| **faq** | a question ≥1 competitor answers that OUR FAQ list does not | ADD an FAQ |
| **link** | an internal-link target/topic ≥2 competitors link that OUR page does not | ADD link / build the page |
| **example** | competitors use a worked example/number/table; OUR section is prose-only | ADD an illustration |
| **quality** | OUR page trails on a quality signal (see content-quality-checklist.md) | FIX on-page SEO |

## Priority (1–3, higher = do first)
`priority = round( coverage_factor × intent_weight )`, clamped to 1–3, where:
- **coverage_factor** = share of competitors that have it: `>=⅔ → 3`, `⅓–⅔ → 2`, `<⅓ → 1`.
- **intent_weight** = how decision-critical the cluster is for the page type:
  - product page: sizing/"how much cover", premium factors, riders, eligibility, claims, trust/CSR → **high (×1.0)**; definitions, types → **medium (×0.8)**; macro/educational → **low (×0.6)**.
  - blog page: definitions, types, examples, FAQs → **high**; product specifics → **low**.
- For **unique** gaps, set priority by how strong a differentiator it is (usually 2).

## Quality score (0–100, OUR page)
Average of the content-quality-checklist.md items that pass, scaled to 100. Report per-brand so
the writer can see exactly where OUR page trails the field.

## Coverage %
`coverage_pct = clusters OUR page covers at depth ≥2  ÷  clusters anyone covers at depth ≥2 × 100`.
