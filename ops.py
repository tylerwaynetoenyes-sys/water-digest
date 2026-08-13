#!/usr/bin/env python3
"""
Operational layer for the water/wastewater digest.

Three things the raw script doesn't do, all of which you need before
anyone pays you:

  1. DEDUP     — only send items the customer hasn't seen
  2. HEALTH    — detect silent failure (a city returning nothing looks
                 identical to a quiet week; this is what kills trust)
  3. COVERAGE  — find out which municipalities are actually on Legistar
                 before you promise a territory

Usage:
    python ops.py coverage --candidates cities.txt   # what's reachable?
    python ops.py run                                # dedup'd digest + draft
    python ops.py health                             # health report only
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import requests

import legistar_digest as core

STATE = Path("state.json")
HEALTH = Path("health.json")

# A city that has produced before but has gone this many DAYS without a
# qualifying item is presumed broken rather than quiet.
#
# Counting runs was wrong: it assumes a weekly cadence, so four manual
# re-runs in one afternoon read as four silent weeks. It also ignored that
# a mid-size city routinely goes a month with no water item on the docket —
# that is a normal council calendar, not a broken scraper.
SILENT_DAYS_BEFORE_ALARM = 45


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save(path: Path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def key(sig) -> str:
    return f"{sig.client}:{sig.file_no}"


# ---------------------------------------------------------------------------
# 1. Coverage — which candidates are actually on Legistar?
# ---------------------------------------------------------------------------
def check_client(client: str) -> tuple[bool, str]:
    try:
        r = requests.get(
            f"{core.API}/{client}/matters", params={"$top": "1"}, timeout=20
        )
        if r.status_code == 200 and isinstance(r.json(), list):
            return True, "ok"
        return False, f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:60]


def cmd_coverage(args) -> None:
    """
    Feed it a newline-delimited file of candidate client codes.
    Legistar codes are usually the city's Granicus subdomain — try the
    city name with no spaces or punctuation first, e.g. 'sanjose'.
    """
    cands = [
        l.strip() for l in Path(args.candidates).read_text().splitlines()
        if l.strip() and not l.startswith("#")
    ]
    live, dead = [], []
    print(f"Testing {len(cands)} candidates...\n", file=sys.stderr)
    for c in cands:
        ok, note = check_client(c)
        (live if ok else dead).append((c, note))
        print(f"  {'✓' if ok else '✗'} {c:<24} {note}", file=sys.stderr)
        time.sleep(0.3)

    print(f"\n{len(live)}/{len(cands)} reachable\n")
    print("# Paste into CITIES in legistar_digest.py")
    print("CITIES = {")
    for c, _ in live:
        print(f'    "{c}": "{c}",')
    print("}")
    if dead:
        print("\n# Not on Legistar (or wrong code) — these need a different"
              "\n# source, or you exclude them and SAY SO in your coverage list:")
        for c, note in dead:
            print(f"#   {c}  ({note})")


# ---------------------------------------------------------------------------
# 2. Health — catch silent failure
# ---------------------------------------------------------------------------
def _days_since(iso):
    if not iso:
        return None
    try:
        return (dt.date.today() - dt.date.fromisoformat(iso)).days
    except ValueError:
        return None


def update_health(per_city_counts: dict) -> list:
    """Returns alarm messages. Measures elapsed days, not run count."""
    health = load(HEALTH, {})
    alarms = []
    today = dt.date.today().isoformat()

    for client, n in per_city_counts.items():
        h = health.setdefault(client, {"ever_produced": False,
                                       "last_hit": None, "empty_runs": 0})
        h.pop("silent_runs", None)          # migrate off the old field
        if n > 0:
            h.update(ever_produced=True, last_hit=today, empty_runs=0)
            continue

        h["empty_runs"] = h.get("empty_runs", 0) + 1
        if not h["ever_produced"]:
            continue                        # never worked = config, not breakage
        gap = _days_since(h["last_hit"])
        if gap is not None and gap >= SILENT_DAYS_BEFORE_ALARM:
            alarms.append(
                f"{client}: no qualifying item in {gap} days "
                f"(last {h['last_hit']}) — likely broken, not quiet"
            )
    save(HEALTH, health)
    return alarms


def cmd_health(args) -> None:
    health = load(HEALTH, {})
    if not health:
        print("No health data yet — run `ops.py run` first.")
        return
    print(f"{'client':<20} {'days quiet':>11}  {'last hit':<12} status")
    for client, h in sorted(health.items()):
        gap = _days_since(h.get("last_hit"))
        if not h.get("ever_produced"):
            status, shown = "never produced (check code)", "-"
        elif gap is not None and gap >= SILENT_DAYS_BEFORE_ALARM:
            status, shown = "!! CHECK", str(gap)
        else:
            status, shown = "ok", str(gap if gap is not None else "-")
        print(f"{client:<20} {shown:>11}  "
              f"{str(h.get('last_hit') or '-'):<12} {status}")


# ---------------------------------------------------------------------------
# 3. Run — dedup'd digest
# ---------------------------------------------------------------------------
def cmd_run(args) -> None:
    seen = set(load(STATE, {"seen": []})["seen"])
    sigs = core.collect(core.CITIES, args.days, args.floor)

    # Health accounting must count ALL cities, including zero-signal ones
    counts = {c: 0 for c in core.CITIES}
    for s in sigs:
        counts[s.client] = counts.get(s.client, 0) + 1
    alarms = update_health(counts)

    fresh = [s for s in sigs if key(s) not in seen]

    if alarms:
        print("\n*** HEALTH ALARMS ***", file=sys.stderr)
        for a in alarms:
            print(f"  {a}", file=sys.stderr)
        print(file=sys.stderr)

    if not fresh:
        print("No new items since last run.", file=sys.stderr)
        save(STATE, {"seen": sorted(seen),
                     "last_run": dt.datetime.now().isoformat(timespec="seconds")})
        return

    md = core.to_markdown(fresh, args.days)
    out = Path(args.out)
    out.write_text(md)

    seen.update(key(s) for s in fresh)
    save(STATE, {"seen": sorted(seen),
                 "last_run": dt.datetime.now().isoformat(timespec="seconds")})

    print(f"{len(fresh)} NEW signals ({len(sigs)} total in window) → {out}",
          file=sys.stderr)

    if not args.no_send:
        send_email(fresh)


def send_email(sigs, subject: str | None = None) -> None:
    """
    Create the issue in Buttondown.

    Defaults to a DRAFT, not a send. Two reasons, and both are the right
    call regardless of tooling: for the first ten subscribers you want to
    read every digest before it goes out — that is how the keyword weights
    get tuned — and a draft makes a bad week visible instead of mailed.

    Flip the repo variable BUTTONDOWN_STATUS to "about_to_send" when you
    are ready for it to send unattended.
    """
    api_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not api_key:
        print("no BUTTONDOWN_API_KEY — skipping send", file=sys.stderr)
        return

    from email_template import to_email_html   # local import: optional dep

    status = os.environ.get("BUTTONDOWN_STATUS", "draft")
    subject = subject or (
        f"Wisconsin water signals — {dt.date.today():%b %-d}")
    # fragment=True: Buttondown wraps this in its own template, so we must
    # not hand it a complete <html> document.
    body = to_email_html(sigs, "Wisconsin", 14,
                         unsubscribe="{{ unsubscribe_url }}", fragment=True)

    r = requests.post(
        "https://api.buttondown.com/v1/emails",
        headers={"Authorization": f"Token {api_key}",
                 "Content-Type": "application/json"},
        json={"subject": subject, "body": body, "status": status},
        timeout=45,
    )
    if r.status_code in (200, 201):
        print(f"buttondown: {status} created ({r.status_code})",
              file=sys.stderr)
    else:
        # Print the body — if the API shape has drifted this is what tells
        # you exactly how, rather than a silent failure.
        print(f"buttondown: HTTP {r.status_code} — {r.text[:400]}",
              file=sys.stderr)


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("coverage")
    c.add_argument("--candidates", required=True)
    c.set_defaults(func=cmd_coverage)

    r = sub.add_parser("run")
    r.add_argument("--days", type=int, default=14)
    r.add_argument("--floor", type=int, default=6)
    r.add_argument("-o", "--out", default="digest.md")
    r.add_argument("--no-send", action="store_true",
                   help="build the digest but do not touch Buttondown")
    r.set_defaults(func=cmd_run)

    h = sub.add_parser("health")
    h.set_defaults(func=cmd_health)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
