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
# All eight below were confirmed live by the coverage check.
# ---------------------------------------------------------------------------
CITIES: dict[str, str] = {
    "milwaukee": "Milwaukee, WI",
    "madison": "Madison, WI",
    "racine": "Racine, WI",
    "waukesha": "Waukesha, WI",
    "manitowoc": "Manitowoc, WI",
    "milwaukeecounty": "Milwaukee County, WI",
    "stpaul": "St. Paul, MN",
    "minneapolismn": "Minneapolis, MN",
}

# ---------------------------------------------------------------------------
# Signal scoring v3 — tuned against the first 24 real items that shipped.
#
#   DOMAIN — water/sewer subject matter. At least one is REQUIRED.
#   STAGE  — position in the buying cycle. Boosts only, never qualifies.
#
# Tune these against customer feedback. This block is the product.
# ---------------------------------------------------------------------------
DOMAIN = {
    # highest intent
    "lead service line": 12, "service line replacement": 12, "lslr": 10,
    "pfas": 10,
    # plant / process equipment — where the big equipment money is
    "water treatment plant": 10, "wastewater treatment": 10,
    "treatment plant": 9, "lift station": 9, "pump station": 9,
    "clarifier": 9, "aeration": 8, "digester": 8, "headworks": 8,
    "disinfection": 8, "filtration": 8, "chlorination": 7, "uv system": 8,
    "sludge": 7, "dewatering": 7, "biosolids": 7, "effluent": 6,
    "scada": 7, "booster station": 8, "reservoir": 6, "water tower": 8,
    "elevated tank": 8,
    # linear infrastructure
    "water main": 8, "watermain": 8, "force main": 8, "sanitary sewer": 7,
    "storm sewer": 6, "sewer lining": 8, "sewer extension": 7,
    "hydrant": 6, "water service": 6,
    # general utility context (weaker, but still domain)
    "wastewater": 6, "water utility": 6, "water works": 6, "sewer": 5,
    "potable water": 6, "drinking water": 6, "stormwater": 5,
    "water supply": 6, "water quality": 4,
}

# ---------------------------------------------------------------------------
# STAGE — buying-cycle position. Boosts only. Never qualifies on its own.
# Earlier stage scores higher: that's the whole product thesis.
# ---------------------------------------------------------------------------
STAGE = {
    "intent to apply": 9, "loan": 6, "priority evaluation": 7,   # 2+ yrs out
    "facility plan": 9, "master plan": 9, "feasibility": 8,      # 1-3 yrs out
    "preliminary design": 8, "capital improvement plan": 7,
    "engineering services": 7, "professional services": 5,       # ~1-2 yrs out
    "request for proposals": 7, "notice to bidders": 8,
    "bid opening": 6, "bids received": 6, "awarding": 6,         # imminent
    "award of contract": 6, "capital improvement": 4,
    "change order": 3, "appropriation": 3,
    "rehabilitation": 5, "expansion": 5,
    # NB: "replacement" and "upgrade" were here and were wrong. They are
    # project *descriptors* ("water main replacement"), not buying stages.
    # Their presence let a purely informational Milwaukee communication
    # register a stage hit and dodge the informational damper.
}

# ---------------------------------------------------------------------------
# NEGATIVE — the project is over, or it's procedural noise.
# ---------------------------------------------------------------------------
NEGATIVE = {
    "approval of minutes": -30, "minutes of the": -30,
    "final payment": -25, "retainage": -25,
    "constructed by private contract": -25, "final acceptance": -25,
    "temporary appointment": -40, "reappointment": -40, "appointment of": -30,
    "internship": -40, "nuisance": -40, "proclamation": -40,
    "receive and file": -12, "annual report": -12,
    "household hazardous waste": -20, "billing module": -20,
    "public library": -40,
    # --- found in the first live digest ---
    "settlement": -30, "claim of": -30, "city attorney": -25,
    "dust control": -35, "vegetation management": -35,
    "comprehensive financial report": -30, "financial report": -25,
    "negotiation strategies": -35, "disposal of real property": -35,
    "closed session": -30, "semi-annual reporting": -30,
    "relating to its": -20,          # Milwaukee's phrasing for FYI items
    "blockage": -20,
}

# An informational communication that merely *mentions* water work is not a
# lead. Milwaukee files a lot of these; they scored high purely on keyword
# density. Damp them unless a real procurement stage is also present.
INFORMATIONAL = ("communication relating to", "communication from the",
                 "relating to the implementation", "providing a review",
                 "reporting to the common council")

# "$30 million" must not parse as $30. That bug understated the single
# biggest item in the first real digest by six orders of magnitude.
MONEY = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s*(million|billion|m\b|bn\b)?", re.I)
MULT = {"million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9}


# ---------------------------------------------------------------------------
# Title cleanup. Municipal clerks paste whole staff reports into the title
# field: "Subject: ... Staff Recommendation: ... Fiscal Note: ...". The
# useful sentence is the first one. Everything after the first boilerplate
# marker is procedural and makes the digest unreadable.
# ---------------------------------------------------------------------------
BOILERPLATE = re.compile(
    r"\s*(Staff Recommendation:|Fiscal Note:|Recommendation:"
    r"|Staff Report:|Background:|Analysis:).*$", re.I | re.S)
LEAD_IN = re.compile(r"^\s*(Subject:|Re:|RE:|SUBJECT:)\s*")


def clean_title(t: str) -> str:
    t = LEAD_IN.sub("", t or "")
    t = BOILERPLATE.sub("", t)
    t = " ".join(t.split()).rstrip(" .,;:-")
    return t + "." if t and t[-1] not in ".?!)" else t


def biggest_amount(text: str):
    best = None
    for num, unit in MONEY.findall(text):
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        if unit:
            v *= MULT.get(unit.lower().strip(), 1)
        best = v if best is None else max(best, v)
    return best


def score(title: str, matter_type: str = "") -> tuple[int, list[str]]:
    low = f"{title} {matter_type}".lower()

    domain_hits = [k for k in DOMAIN if k in low]
    if not domain_hits:
        return 0, []                      # THE GATE — no water, no entry

    pts = max(DOMAIN[k] for k in domain_hits)          # best domain match
    pts += sum(DOMAIN[k] for k in domain_hits) // 4    # small breadth bonus

    stage_hits = [k for k in STAGE if k in low]
    pts += max((STAGE[k] for k in stage_hits), default=0)

    for k, w in NEGATIVE.items():
        if k in low:
            pts += w

    # Informational filings mention the work without being the work.
    if any(p in low for p in INFORMATIONAL) and not stage_hits:
        pts -= 18

    amt = biggest_amount(title)
    if amt:
        if amt >= 5_000_000:
            pts += 10
        elif amt >= 500_000:
            pts += 6
        elif amt >= 50_000:
            pts += 3

    return pts, domain_hits + stage_hits


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
        r = requests.get(f"{API}/{client}/matters", params=params,
                         timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ! {client}: HTTP {r.status_code}", file=sys.stderr)
            return []
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  ! {client}: {e}", file=sys.stderr)
        return []


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
                # Display the cleaned title, but score and extract the
                # amount from the RAW one — the dollar figure usually lives
                # inside the "Fiscal Note:" boilerplate we strip.
                title=clean_title(title),
                intro_date=(m.get("MatterIntroDate") or "")[:10],
                matter_type=m.get("MatterTypeName", ""),
                status=m.get("MatterStatusName", ""),
                score=pts,
                amount=biggest_amount(title),
                matched=hits,
            ))
        time.sleep(0.4)  # be a good citizen
    return sorted(out, key=lambda s: -s.score)


def to_markdown(sigs: Iterable[Signal], days: int) -> str:
    sigs = list(sigs)
    today = dt.date.today().isoformat()
    money = [s.amount for s in sigs if s.amount]
    lines = [
        "# Municipal Water & Wastewater Signal Digest",
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
        r = requests.get(f"{API}/{a.check}/matters",
                         params={"$top": "1"}, timeout=TIMEOUT)
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
