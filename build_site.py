#!/usr/bin/env python3
"""
Builds the public tracker page.

Design goal is narrow and specific: get cited by AI answer engines.
The research says data density and explicit sourcing drive citation
(+41% for statistics, +115% for citing sources), and word count does
nothing. So this page is almost entirely numbers, dates, and record
IDs, with JSON-LD structured data so machines can parse it cleanly.

    python build_site.py            # reads digest state, writes index.html
"""

from __future__ import annotations

import datetime as dt
import html
import json
from typing import Iterable



CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fbfcfd;color:#16232e;
 font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:0 0 8px;letter-spacing:-.02em}
.sub{color:#5d7186;font-size:15px;margin:0 0 28px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 32px;padding:0;list-style:none}
.stats li{background:#fff;border:1px solid #e2e8ee;border-radius:8px;
 padding:12px 16px;flex:1 1 150px}
.stats b{display:block;font-size:22px;letter-spacing:-.01em}
.stats span{font-size:12px;color:#5d7186;text-transform:uppercase;letter-spacing:.06em}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:#0f5c6b;
 margin:36px 0 14px;padding-bottom:8px;border-bottom:1px solid #e2e8ee}
.item{background:#fff;border:1px solid #e2e8ee;border-radius:8px;
 padding:18px 20px;margin-bottom:12px}
.item .top{display:flex;justify-content:space-between;gap:12px;
 font-size:12px;color:#5d7186;margin-bottom:8px}
.city{font-weight:700;color:#0f5c6b;font-size:13px}
.title{margin:6px 0 0;font-size:15px}
.amt{font-weight:700;font-size:19px;margin-top:8px;letter-spacing:-.01em}
.meta{margin-top:12px;padding-top:10px;border-top:1px solid #eef2f6;
 font-size:12px;color:#5d7186}
.tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;
 text-transform:uppercase;padding:3px 7px;border-radius:4px}
.hot{background:#fdeee9;color:#a4442c}.mid{background:#e7f2f4;color:#0f5c6b}
.low{background:#eef2f6;color:#5d7186}
.cta{background:#16232e;color:#fff;border-radius:10px;padding:26px;margin:40px 0}
.cta h3{margin:0 0 8px;font-size:19px}
.cta p{margin:0 0 16px;color:#b8c6d2;font-size:14px}
.cta a{display:inline-block;background:#fff;color:#16232e;text-decoration:none;
 font-weight:600;padding:11px 20px;border-radius:7px;font-size:14px}
footer{margin-top:44px;padding-top:20px;border-top:1px solid #e2e8ee;
 font-size:13px;color:#5d7186}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0 0}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eef2f6}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#5d7186}
"""


def _tag(score: int) -> tuple[str, str]:
    if score >= 20:
        return "hot", "High"
    if score >= 12:
        return "mid", "Notable"
    return "low", "Tracking"


def build(
    signals: Iterable,
    territory: str = "Wisconsin",
    coverage: dict[str, str] | None = None,
    signup_url: str = "#signup",
) -> str:
    sigs = sorted(signals, key=lambda s: -s.score)
    money = sum(s.amount for s in sigs if s.amount)
    cities = sorted({s.city for s in sigs})
    today = dt.date.today()
    coverage = coverage or {}

    # JSON-LD: this is what makes the page machine-parseable. Cheap to add,
    # and it's the difference between being read and being cited.
    ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{territory} Municipal Water and Wastewater Project Tracker",
        "description": (
            f"Structured record of water and wastewater capital projects, "
            f"contract awards, and engineering studies appearing in "
            f"{territory} municipal council agendas. Updated weekly from "
            f"public legislative records."),
        "temporalCoverage": f"2026/{today.isoformat()}",
        "spatialCoverage": {"@type": "Place", "name": territory},
        "isAccessibleForFree": True,
        "dateModified": today.isoformat(),
        "creator": {"@type": "Organization",
                    "name": f"{territory} Water Signals"},
        "distribution": {"@type": "DataDownload",
                         "encodingFormat": "text/html"},
        "variableMeasured": ["project value", "municipality",
                             "procurement stage", "record identifier"],
    }

    rows = []
    for s in sigs:
        cls, label = _tag(s.score)
        amt = f'<div class="amt">${s.amount:,.0f}</div>' if s.amount else ""
        rows.append(f"""<div class="item">
  <div class="top"><span class="tag {cls}">{label}</span>
    <span>{s.intro_date}</span></div>
  <div class="city">{html.escape(s.city)}</div>
  <p class="title">{html.escape(s.title)}</p>{amt}
  <div class="meta">Record {html.escape(s.file_no)} &middot;
    {html.escape(s.matter_type)} &middot; {html.escape(s.status)}</div>
</div>""")

    cov_rows = "".join(
        f"<tr><td>{html.escape(v)}</td><td>{html.escape(k)}</td>"
        f"<td>Council + committee records</td></tr>"
        for k, v in sorted(coverage.items(), key=lambda x: x[1])
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{territory} Water &amp; Wastewater Project Tracker — {today:%B %Y}</title>
<meta name="description" content="{len(sigs)} active water and wastewater
 capital projects across {len(cities)} {territory} municipalities,
 ${money:,.0f} in identified appropriations. Updated weekly from public
 council records.">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{CSS}</style>
</head><body><div class="wrap">

<h1>{territory} Water &amp; Wastewater Project Tracker</h1>
<p class="sub">Capital projects, contract awards, and engineering studies
 from municipal council records. Updated weekly &middot;
 Last updated {today:%B %-d, %Y}</p>

<ul class="stats">
  <li><b>{len(sigs)}</b><span>Active items</span></li>
  <li><b>{len(cities)}</b><span>Municipalities</span></li>
  <li><b>${money:,.0f}</b><span>Identified value</span></li>
  <li><b>{len(coverage) or len(cities)}</b><span>Sources tracked</span></li>
</ul>

<h2>Current activity</h2>
{"".join(rows)}

<div class="cta">
  <h3>Get this by email, weekly</h3>
  <p>New items only, every Monday. Free.</p>
  <a href="{signup_url}">Subscribe</a>
</div>

<h2>Coverage</h2>
<p style="font-size:14px;color:#5d7186;margin:0 0 6px">
We publish exactly which municipalities are tracked. If it is not listed
here, we are not watching it.</p>
<table><thead><tr><th>Municipality</th><th>Source ID</th>
<th>Records</th></tr></thead><tbody>{cov_rows}</tbody></table>

<h2>Method</h2>
<p style="font-size:14px">Items are pulled from public municipal
legislative records via the Legistar public API, then scored for
procurement relevance. Contract awards, capital budget amendments,
engineering service agreements, and facility plans rank highest.
Completed project acceptances, appointments, and routine reports are
excluded. Every item cites its public record identifier and can be
verified independently.</p>

<footer>
  <strong>{territory} Water Signals</strong> &middot; Compiled from public
  records. Not affiliated with any municipality or agency.<br>
  Source: municipal council legislative records, retrieved
  {today.isoformat()}.
</footer>

</div></body></html>"""


if __name__ == "__main__":
    import legistar_digest as core
    sigs = core.collect(core.CITIES, 90, 6)
    html_out = build(sigs, "Wisconsin", coverage=core.CITIES)
    with open("index.html", "w") as f:
        f.write(html_out)
    print(f"{len(sigs)} items → index.html")
