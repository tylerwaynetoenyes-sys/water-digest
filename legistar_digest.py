#!/usr/bin/env python3
"""
Municipal Water/Wastewater Project Digest
------------------------------------------
Pulls council agenda matters from Legistar-hosted municipalities,
filters for water/wastewater capital activity, scores by buying-signal
strength, and emits a digest.

Legistar runs a free, unauthenticated public API. No key, no scraping,
no ToS to accept. Roughly 2,000+ US municipalities use it.

Usage:
    python legistar_digest.py                    # last 60 days, default cities
    python legistar_digest.py --days 30
    python legistar_digest.py --check denver     # verify a client code works

Requires: pip install requests
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable

import requests

API = "https://webapi.legistar.com/v1"
TIMEOUT = 30

# ---------------------------------------------------------------------------
# Target municipalities. Legistar client codes are usually the city's Granicus
# subdomain. Verify a new one with:  python legistar_digest.py --check <code>
# These three are confirmed working.
# ---------------------------------------------------------------------------
CITIES: dict[str, str] = {
    # --- Wisconsin: CONFIRMED working (tested live) ---
    "milwaukee": "Milwaukee, WI",
    "madison": "Madison, WI",
    "racine": "Racine, WI",
    # --- Adjacent, confirmed ---
    "stpaul": "St. Paul, MN",
    # Run `python ops.py coverage --candidates wi_candidates.txt` to find
    # the rest. Confirmed NOT working under the obvious code: chicago,
    # evanston, greenbay, minneapolis — they need a different client code
    # or a non-Legistar source.
}

# ---------------------------------------------------------------------------
# Signal scoring. This is the actual product — the keyword weighting is what
# separates "a scraper" from "intelligence someone pays for". Tune it against
# real customer feedback; that tuning becomes your moat.
# ---------------------------------------------------------------------------
HIGH_VALUE = {
    "lead service line": 10, "lead water line": 10, "service line replacement": 10,
    "pfas": 9, "water treatment plant": 9, "wastewater treatment": 9,
    "wastewater": 7, "emergency construction": 8, "construction contract": 5,
    "design and construction": 6, "appropriation": 4, "bid award": 6,
    "water main": 8, "sewer main": 8, "lift station": 8, "pump station": 8,
    "capital improvement": 7, "water infrastructure": 7, "force main": 7,
    "clarifier": 7, "aeration": 7, "sludge": 6, "dewatering": 6,
    "filtration": 6, "disinfection": 6, "chlorination": 6,
    "reservoir": 5, "stormwater": 5, "drainage": 4, "watermain": 8,
    "sanitary sewer": 7, "potable water": 6, "water quality": 4,
    # --- procurement-stage words: this is where the money actually is ---
    "awarding": 9, "award of contract": 9, "capital budget": 8,
    "engineering services": 8, "professional services": 5,
    "feasibility": 7, "preliminary design": 8, "facility plan": 8,
    "study": 4, "request for proposals": 8, "notice to bidders": 8,
}

# Phrases that mean the money is already spent or was never yours to win.
# Getting these wrong is what makes a digest feel like spam — the customer
# opens it, sees three completed subdivisions, and never opens it again.
NEGATIVE = {
    "constructed by private contract": -14,  # developer built it, already done
    "accepting": -6,                          # acceptance = project is over
    "final acceptance": -10,
    "temporary appointment": -20,
    "reappointment": -20,
    "internship": -20,
    "nuisance": -20,
    "annual report": -8,
    "compliance maintenance annual report": -12,
}

# Matter types that indicate real money moving vs. procedural noise
TYPE_BOOST = {
    "bill": 4, "ordinance": 4, "resolution": 3, "contract": 5,
    "new business": 3, "public hearing": 2, "presentation": 2,
    "consent calendar": 1,
}
TYPE_PENALTY = {
    "appointment": -8, "minutes approval": -10, "proclamation": -8,
    "closed session": -3, "information item": -1,
}

MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


@dataclass
class Signal:
    city: str
    client: str
    file_no: str
    title: str
    intro_date: str
    matter_type: str
    status: str
    score: int = 0
    amount: float | None = None
    matched: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://{self.client}.legistar.com/Legislation.aspx"


def fetch_matters(client: str, since: dt.date, top: int = 200) -> list[dict]:
    """Pull matters introduced since `since` for one Legistar client."""
    params = {
        "$filter": f"MatterIntroDate gt datetime'{since.isoformat()}'",
        "$orderby": "MatterIntroDate desc",
        "$top": str(top),
    }
    try:
        r = requests.get(f"{API}/{client}/matters", params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ! {client}: HTTP {r.status_code}", file=sys.stderr)
            return []
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  ! {client}: {e}", file=sys.stderr)
        return []


def score(title: str, matter_type: str) -> tuple[int, list[str]]:
    low = title.lower()
    pts, hits = 0, []
    for kw, w in HIGH_VALUE.items():
        if kw in low:
            pts += w
            hits.append(kw)
    if not hits:
        return 0, []

    for kw, w in NEGATIVE.items():
        if kw in low:
            pts += w

    t = (matter_type or "").lower()
    for frag, w in TYPE_BOOST.items():
        if frag in t:
            pts += w
            break
    for frag, w in TYPE_PENALTY.items():
        if frag in t:
            pts += w
            break

    # Dollar figures in the title mean a real appropriation
    if MONEY.search(title):
        pts += 6
    return pts, hits


def biggest_amount(title: str) -> float | None:
    vals = [float(m.replace(",", "")) for m in MONEY.findall(title)]
    return max(vals) if vals else None


def collect(cities: dict[str, str], days: int, floor: int = 6) -> list[Signal]:
    since = dt.date.today() - dt.timedelta(days=days)
    out: list[Signal] = []
    for client, label in cities.items():
        print(f"  → {label} ({client})", file=sys.stderr)
        for m in fetch_matters(client, since):
            title = (m.get("MatterTitle") or m.get("MatterName") or "").strip()
            if not title:
                continue
            pts, hits = score(title, m.get("MatterTypeName", ""))
            if pts < floor:
                continue
            out.append(Signal(
                city=label,
                client=client,
                file_no=m.get("MatterFile", ""),
                title=" ".join(title.split()),
                intro_date=(m.get("MatterIntroDate") or "")[:10],
                matter_type=m.get("MatterTypeName", ""),
                status=m.get("MatterStatusName", ""),
                score=pts,
                amount=biggest_amount(title),
                matched=hits,
            ))
        time.sleep(0.4)  # be a good citizen
    out.sort(key=lambda s: (-s.score, s.intro_date), reverse=False)
    return sorted(out, key=lambda s: -s.score)


def to_markdown(sigs: Iterable[Signal], days: int) -> str:
    sigs = list(sigs)
    today = dt.date.today().isoformat()
    money = [s.amount for s in sigs if s.amount]
    lines = [
        f"# Municipal Water & Wastewater Signal Digest",
        f"*{today} — activity from the last {days} days*",
        "",
        f"**{len(sigs)} relevant items** across {len({s.city for s in sigs})} "
        f"municipalities."
        + (f" **${sum(money):,.0f}** in identified appropriations." if money else ""),
        "",
        "---",
        "",
    ]
    for s in sigs:
        flag = "🔴" if s.score >= 18 else ("🟠" if s.score >= 12 else "🟡")
        lines.append(f"### {flag} {s.city} — {s.file_no}")
        lines.append("")
        lines.append(f"**{s.title}**")
        lines.append("")
        bits = [f"`{s.intro_date}`", f"*{s.matter_type}*", f"status: {s.status}"]
        if s.amount:
            bits.append(f"**${s.amount:,.0f}**")
        lines.append(" · ".join(bits))
        lines.append("")
        lines.append(f"<sub>signal {s.score} · matched: {', '.join(s.matched)}</sub>")
        lines.append("")
    lines += ["---", "", "<sub>Source: Legistar public API. Public records.</sub>"]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--floor", type=int, default=6, help="min signal score")
    p.add_argument("--check", metavar="CLIENT", help="test one client code")
    p.add_argument("--json", action="store_true")
    p.add_argument("-o", "--out", default="digest.md")
    a = p.parse_args()

    if a.check:
        r = requests.get(f"{API}/{a.check}/matters", params={"$top": "1"}, timeout=TIMEOUT)
        print(f"{a.check}: HTTP {r.status_code}")
        if r.status_code == 200:
            print(json.dumps(r.json()[:1], indent=2)[:600])
        return

    print(f"Scanning {len(CITIES)} municipalities...", file=sys.stderr)
    sigs = collect(CITIES, a.days, a.floor)

    if a.json:
        print(json.dumps([asdict(s) for s in sigs], indent=2))
        return

    md = to_markdown(sigs, a.days)
    with open(a.out, "w") as f:
        f.write(md)
    print(f"\n{len(sigs)} signals → {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
