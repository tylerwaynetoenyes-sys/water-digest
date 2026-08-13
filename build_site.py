#!/usr/bin/env python3
"""
Builds the public tracker page.

Ported from the approved Claude Design revision. Two changes from the
mockup, both deliberate:

  · Inline styles became classes driven by custom properties, so
    prefers-color-scheme switches automatically instead of needing a
    second hand-built page.
  · The quiet-week variant is now a state the code enters on its own
    when volume is low, rather than a separate mockup.

Semantic HTML is a requirement, not a preference: AI answer engines are
a primary distribution channel and structure is what they parse. It also
fixes screen readers and 200% reflow for a 45-65 readership.

    python build_site.py            # writes index.html
"""

from __future__ import annotations

import datetime as dt
import html
import json
from typing import Iterable

from design import (LIGHT, DARK, SANS, MONO, css_vars, stage_of, money,
                    dateline)

QUIET_THRESHOLD = 8          # below this many items, the page changes voice

CSS = f"""
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-text-size-adjust:100%}}
body{{background:var(--bg);color:var(--ink);font-family:{SANS};
 font-size:17px;line-height:1.55;font-variant-numeric:tabular-nums;
 -webkit-font-smoothing:antialiased}}
main{{display:block;max-width:1080px;margin:0 auto;background:var(--bg)}}
a{{color:var(--design)}}
h1,h2,h3{{font-weight:inherit}}

.mast{{display:block;padding:26px 56px 18px}}
.mast-row{{display:flex;align-items:baseline;justify-content:space-between;gap:24px}}
.wordmark{{font-size:28px;font-weight:700;letter-spacing:-.02em;color:var(--ink)}}
.tagline{{font-size:17px;color:var(--secondary);margin-top:3px}}
.contact{{text-align:right;font-size:16px;color:var(--secondary);line-height:1.45}}

.build{{margin:0;padding:10px 56px;font-family:{MONO};font-size:15px;
 letter-spacing:.04em;color:var(--secondary);
 border-top:1px solid var(--line);border-bottom:1px solid var(--line);
 display:flex;gap:26px;flex-wrap:wrap}}
.build strong{{color:var(--ink);font-weight:600}}

.hero{{display:block;padding:44px 56px 34px}}
.hero-grid{{display:grid;grid-template-columns:1.3fr 1fr;gap:56px;align-items:start}}
h1{{font-size:44px;line-height:1.12;letter-spacing:-.024em;font-weight:700;
 text-wrap:balance}}
.dek{{margin-top:16px;font-size:20px;line-height:1.5;color:var(--body);
 text-wrap:pretty}}
.pull{{margin-top:16px;font-size:19px;line-height:1.5;color:var(--design);
 font-weight:600;text-wrap:pretty}}
.provenance{{font-size:17px;line-height:1.6;color:var(--secondary);
 text-wrap:pretty}}

.figures{{display:block;padding:0 56px 40px}}
h2{{font-size:15px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
 color:var(--secondary);margin-bottom:14px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
 border-top:1px solid var(--line-hard);border-bottom:1px solid var(--line)}}
.stats>div{{padding:22px 28px}}
.stats>div+div{{border-left:1px solid var(--line)}}
.stats>div:first-child{{padding-left:0}}
.stats dd{{font-size:31px;font-weight:700;letter-spacing:-.028em;line-height:1.1;
 color:var(--ink)}}
.stats dt{{margin-top:9px;font-family:{MONO};font-size:15px;letter-spacing:.08em;
 text-transform:uppercase;color:var(--secondary)}}
.figures>p{{margin-top:12px;font-size:16px;line-height:1.55;
 color:var(--secondary);max-width:820px}}

.records{{display:block;padding:0 56px 40px}}
.rec-head{{display:flex;justify-content:space-between;align-items:baseline;
 margin-bottom:16px}}
.rec-head p{{font-size:16px;color:var(--secondary)}}
.rows{{display:grid;grid-template-columns:118px 1fr 190px;gap:0 32px}}
.colhead{{display:contents}}
.colhead span{{font-family:{MONO};font-size:15px;letter-spacing:.08em;
 text-transform:uppercase;color:var(--secondary);
 padding-bottom:10px;border-bottom:1px solid var(--line-hard)}}
.colhead span:last-child{{text-align:right}}
article{{grid-column:1/-1;display:grid;grid-template-columns:subgrid;
 padding:20px 0;border-bottom:1px solid var(--line)}}
.chip{{display:inline-block;font-size:15px;font-weight:700;letter-spacing:.08em;
 border-radius:3px}}
.chip.filled{{color:var(--on-fill);padding:4px 9px}}
.chip.outlined{{background:transparent;border:1.5px solid;padding:2.5px 7.5px}}
.chip.planning.filled{{background:var(--planning)}}
.chip.bidding.filled{{background:var(--bidding)}}
.chip.design.outlined{{color:var(--design);border-color:var(--design)}}
.chip.tracking.outlined{{color:var(--secondary);border-color:var(--secondary)}}
.sub{{display:block;margin-top:5px;font-size:16px;color:var(--secondary)}}
article h3{{font-size:19px;line-height:1.45;font-weight:500;text-wrap:pretty;
 color:var(--ink)}}
.meta{{margin-top:9px;font-family:{MONO};font-size:16px;color:var(--secondary)}}
.meta .place{{color:var(--ink);font-weight:600}}
.amount{{text-align:right;font-size:32px;font-weight:700;letter-spacing:-.028em;
 line-height:1.1;color:var(--ink)}}
.amount.none{{font-family:{MONO};font-size:15px;font-weight:400;
 letter-spacing:.06em;color:var(--secondary)}}

.two{{padding:0 56px 40px;display:grid;grid-template-columns:1fr 1fr;gap:56px;
 align-items:start}}
table{{width:100%;border-collapse:collapse;font-size:17px}}
th{{text-align:left;font-family:{MONO};font-size:15px;letter-spacing:.08em;
 text-transform:uppercase;color:var(--secondary);font-weight:400;
 padding-bottom:10px;border-bottom:1px solid var(--line-hard)}}
td{{padding:11px 0;border-bottom:1px solid var(--line);color:var(--body)}}
td:first-child{{color:var(--ink)}}
.lede{{font-size:19px;font-weight:600;line-height:1.45;margin-bottom:16px;
 color:var(--ink)}}
ol{{list-style:none;counter-reset:m}}
ol li{{counter-increment:m;position:relative;padding-left:38px;
 margin-bottom:12px;font-size:17px;line-height:1.55;color:var(--body)}}
ol li::before{{content:"0" counter(m);position:absolute;left:0;
 font-family:{MONO};font-size:15px;color:var(--secondary)}}

.sub-block{{margin:0 56px 40px;padding:30px 34px;background:var(--surface);
 border:1px solid var(--line)}}
.sub-block p{{font-size:19px;font-weight:600;margin-bottom:14px;color:var(--ink)}}
.sub-block .fine{{font-size:16px;font-weight:400;color:var(--secondary);
 margin-bottom:18px}}
.attrib{{margin-top:14px;font-size:15px;font-weight:400}}
.attrib a{{color:var(--secondary);text-decoration:none}}
form{{display:flex;gap:10px;flex-wrap:wrap}}
input{{flex:1 1 260px;font:400 17px {SANS};padding:13px 15px;
 border:1px solid var(--line-hard);background:var(--bg);color:var(--ink)}}
button{{font:600 17px {SANS};padding:13px 28px;border:none;cursor:pointer;
 background:var(--design);color:var(--on-fill)}}

footer{{padding:26px 56px 44px;border-top:1px solid var(--line);
 display:grid;grid-template-columns:1fr 1fr 1.3fr;gap:36px;
 font-size:16px;line-height:1.6;color:var(--secondary)}}
footer strong{{display:block;color:var(--ink);font-weight:600}}

@media(max-width:820px){{
 .hero-grid,.two,footer{{grid-template-columns:1fr;gap:26px}}
 .rows{{grid-template-columns:1fr}}
 article{{grid-template-columns:1fr;gap:10px}}
 .colhead{{display:none}}
 .amount{{text-align:left;font-size:28px}}
 .mast,.hero,.figures,.records,.two,footer{{padding-left:20px;padding-right:20px}}
 .build{{padding-left:20px;padding-right:20px;gap:14px}}
 .sub-block{{margin-left:20px;margin-right:20px}}
 h1{{font-size:34px}}
}}
@media print{{body{{background:#fff}} .sub-block{{display:none}}}}
"""


def _row(s) -> str:
    key, label, sub, shape = stage_of(s.matched, s.score)
    place, stamp = dateline(s.city, s.intro_date)
    amt = (f'<p class="amount">{money(s.amount)}</p>' if s.amount
           else '<p class="amount none">NO AMOUNT IN RECORD</p>')
    bits = " · ".join(x for x in [f"RECORD {s.file_no}" if s.file_no else "",
                                  s.matter_type.upper(), s.status.upper()] if x)
    return f"""<article>
<p><span class="chip {key} {shape}">{label}</span>{
   f'<span class="sub">{sub}</span>' if sub else ''}</p>
<div>
<h3>{html.escape(s.title)}</h3>
<p class="meta"><span class="place">{html.escape(place)}</span> — <time
 datetime="{s.intro_date}">{stamp}</time> · {html.escape(bits)}</p>
</div>
{amt}
</article>"""


def build(signals: Iterable, territory: str = "Wisconsin",
          coverage: dict[str, str] | None = None, silent: int = 0,
          editor: str = "Tyler Toenyes", phone: str = "(314) 267-4194",
          place: str = "Alton, Illinois",
          handle: str = "Tyler_T") -> str:
    sigs = sorted(signals, key=lambda s: -s.score)
    coverage = coverage or {}
    total = sum(s.amount for s in sigs if s.amount)
    today = dt.date.today()
    nxt = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
    quiet = len(sigs) < QUIET_THRESHOLD

    earliest = "—"
    for s in sigs:
        for tok in s.title.replace(",", " ").split():
            if tok.upper().startswith("FY") and tok[2:].isdigit():
                earliest = min(earliest, tok.upper()) if earliest != "—" else tok.upper()

    dek = (f"Every water and wastewater item from municipal council records "
           f"across {len(coverage) or len({s.city for s in sigs})} "
           f"{territory} and upper-Midwest municipalities. Loan applications, "
           f"facility plans, contract awards. The Monday digest is free, and "
           f"stays free.")
    if quiet:
        dek = ("A quiet week. Council calendars run in cycles: budget season "
               "crowds the docket, late summer and holiday weeks empty it. "
               "This week is one of the empty ones, and we publish it exactly "
               "as it came in. Free, and stays free — quiet weeks included.")

    ld = {"@context": "https://schema.org", "@type": "Dataset",
          "name": f"{territory} Municipal Water and Wastewater Project Tracker",
          "description": (
              f"{len(sigs)} active water and wastewater capital projects "
              f"across {len(coverage)} {territory} and upper-Midwest "
              f"municipalities, representing ${total:,.0f} in identified "
              f"appropriations. Compiled weekly from public municipal "
              f"legislative records via the Legistar public API."),
          "temporalCoverage": f"2026/{today.isoformat()}",
          "spatialCoverage": {"@type": "Place", "name": territory},
          "isAccessibleForFree": True, "dateModified": today.isoformat(),
          "creator": {"@type": "Person", "name": editor},
          "publisher": {"@type": "Organization",
                        "name": f"{territory} Water Signals"},
          "variableMeasured": ["project value", "municipality",
                               "procurement stage", "record identifier"]}

    cov = "".join(f"<tr><td>{html.escape(v)}</td><td>{html.escape(k)}</td>"
                  f"<td>Council &amp; committee</td></tr>"
                  for k, v in sorted(coverage.items(), key=lambda x: x[1]))

    stat = lambda n, l: f"<div><dd>{n}</dd><dt>{l}</dt></div>"  # noqa: E731

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{territory} Water &amp; Wastewater Project Tracker</title>
<meta name="description" content="{len(sigs)} active water and wastewater capital projects across {len(coverage)} {territory} municipalities. ${total:,.0f} identified. Rebuilt weekly from public council records.">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>
:root{{{css_vars(LIGHT)}}}
@media (prefers-color-scheme:dark){{:root{{{css_vars(DARK)}}}}}
{CSS}
</style>
</head><body>
<main>

<header class="mast">
 <div class="mast-row">
  <div>
   <p class="wordmark">{territory} Water Signals</p>
   <p class="tagline">Municipal water &amp; wastewater capital projects ·
    {territory} and upper Midwest</p>
  </div>
  <p class="contact">Updated weekly<br><a href="tel:+13142674194">{phone}</a></p>
 </div>
</header>

<p class="build">
 <span>LAST BUILD <strong><time datetime="{today.isoformat()}">{today:%Y-%m-%d} 06:00 CT</time></strong></span>
 <span>NEXT BUILD <time datetime="{nxt.isoformat()}">{nxt:%Y-%m-%d} 06:00 CT</time>
  · {len(coverage)} SOURCES · {len(sigs)} ITEMS{f' · {silent} SILENT' if silent else ''}</span>
</p>

<section class="hero">
 <div class="hero-grid">
  <div>
   <h1>{territory} water projects, months before they hit bid.</h1>
   <p class="dek">{dek}</p>
   <p class="pull">The deal is usually decided before the RFP is published.</p>
  </div>
  <div>
   <p class="provenance">Items are drawn from published council and committee
   records only. Nothing here is confidential, and nothing here is a
   forecast — each entry is a document a municipality has already filed,
   carrying its own public record number.</p>
  </div>
 </div>
</section>

<section class="figures">
 <h2>Current set · in figures</h2>
 <dl class="stats">
  {stat(money(total) if total else '—', 'Identified project value')}
  {stat(len(sigs), 'Active items')}
  {stat(len(coverage), 'Municipalities tracked')}
  {stat(earliest, 'Earliest funding year filed')}
 </dl>
 <p>Dollar figures are taken from the record itself. Where a record states
 no amount, none is shown — nothing is estimated.</p>
</section>

<section class="records">
 <div class="rec-head">
  <h2>Records · week of <time datetime="{today.isoformat()}">{today:%b %-d, %Y}</time></h2>
  <p>{len(sigs)} shown · full list in Monday's email</p>
 </div>
 <div class="rows">
  <div class="colhead"><span>Stage</span><span>Item · public record</span><span>Value</span></div>
  {''.join(_row(s) for s in sigs)}
 </div>
</section>

<div class="sub-block">
 <p>Monday's digest, by email.</p>
 <p class="fine">Free, and stays free. Every Monday. Unsubscribe anytime.</p>
 <form action="https://buttondown.com/api/emails/embed-subscribe/{handle}"
  method="post" class="embeddable-buttondown-form" target="popupwindow"
  onsubmit="window.open('https://buttondown.com/{handle}','popupwindow')">
  <label for="bd-email" hidden>Email address</label>
  <input id="bd-email" name="email" type="email"
   placeholder="Email address" required>
  <button type="submit">Subscribe</button>
 </form>
 <p class="attrib"><a href="https://buttondown.com/refer/{handle}"
  target="_blank" rel="noopener">Powered by Buttondown</a></p>
</div>

<div class="two">
 <section>
  <h2>Coverage · {len(coverage)} sources</h2>
  <p class="lede">If a municipality isn't on this list, we're not watching it.</p>
  <table><thead><tr><th scope="col">Municipality</th><th scope="col">Source</th>
  <th scope="col">Records</th></tr></thead><tbody>{cov}</tbody></table>
 </section>
 <section>
  <h2>Method</h2>
  <ol>
   <li>Records are retrieved from public municipal legislative records via
   the Legistar public API.</li>
   <li>Loan applications, facility plans and capital budget amendments rank
   highest because they surface earliest.</li>
   <li>Completed acceptances, final payments and appointments are excluded.</li>
   <li>Every item carries a public record identifier and can be verified
   independently.</li>
  </ol>
 </section>
</div>

<footer>
 <div><strong>{territory} Water Signals</strong>{place}</div>
 <div><strong>Contact</strong>{editor}, editor<br>
  <a href="tel:+13142674194">{phone}</a></div>
 <div>Compiled from public records. Not affiliated with any municipality
  or agency.</div>
</footer>

</main></body></html>"""


if __name__ == "__main__":
    import legistar_digest as core
    sigs = core.collect(core.CITIES, 90, 6)
    seen = {s.client for s in sigs}
    with open("index.html", "w") as f:
        f.write(build(sigs, "Wisconsin", coverage=core.CITIES,
                      silent=len(core.CITIES) - len(seen)))
    print(f"{len(sigs)} items → index.html")
