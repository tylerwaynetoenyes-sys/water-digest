#!/usr/bin/env python3
"""
Email rendering for the digest.

The page can use custom properties, subgrid and prefers-color-scheme.
Email cannot — municipal reps read mail in Outlook, which renders HTML
with Microsoft Word's engine. So: nested tables, inline styles, no web
fonts, 600px, belt-and-braces.

The design language carries across intact: same palette, same stage
chips (filled / outlined / filled — the shape channel matters more here,
since Outlook mangles colour more often than it mangles borders), same
AP dateline, money as the hero, 15px floor.

    from email_template import to_email_html, to_plaintext
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from design import LIGHT as P, SANS, stage_of, money, dateline

MONO = "Consolas,'Courier New',monospace"


def _chip(key: str, label: str, shape: str) -> str:
    if shape == "filled":
        bg = P[key] if key in P else P["secondary"]
        return (f'<span style="display:inline-block;font:700 15px/1 {SANS};'
                f'letter-spacing:.08em;color:#fff;background:{bg};'
                f'padding:4px 9px;border-radius:3px;">{label}</span>')
    col = P.get(key, P["secondary"])
    return (f'<span style="display:inline-block;font:700 15px/1 {SANS};'
            f'letter-spacing:.08em;color:{col};background:transparent;'
            f'border:1.5px solid {col};padding:2.5px 7.5px;'
            f'border-radius:3px;">{label}</span>')


def _row(s) -> str:
    key, label, sub, shape = stage_of(s.matched, s.score)
    place, stamp = dateline(s.city, s.intro_date)
    amount = (f'<div style="font:700 30px/1.1 {SANS};color:{P["ink"]};'
              f'letter-spacing:-.028em;">{money(s.amount)}</div>'
              if s.amount else
              f'<div style="font:400 15px/1.3 {MONO};letter-spacing:.06em;'
              f'color:{P["secondary"]};">NO AMOUNT IN RECORD</div>')
    bits = " · ".join(x for x in [f"RECORD {s.file_no}" if s.file_no else "",
                                  s.matter_type.upper(), s.status.upper()] if x)
    return f"""
<tr><td style="padding:20px 0;border-bottom:1px solid {P['line']};">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
   <td valign="top" style="padding-bottom:12px;">{_chip(key, label, shape)}{
     f'<div style="margin-top:5px;font:400 16px/1.3 {SANS};color:{P["secondary"]};">{sub}</div>'
     if sub else ''}</td>
   <td valign="top" align="right" style="padding-bottom:12px;">{amount}</td>
  </tr>
  <tr><td colspan="2" style="font:500 19px/1.45 {SANS};color:{P['ink']};">
    {s.title}</td></tr>
  <tr><td colspan="2" style="padding-top:9px;font:400 16px/1.4 {MONO};
    color:{P['secondary']};">
    <span style="color:{P['ink']};font-weight:600;">{place}</span> &mdash;
    {stamp} · {bits}</td></tr>
 </table>
</td></tr>"""


def to_email_html(signals: Iterable, territory: str = "Wisconsin",
                  days: int = 14, unsubscribe: str = "#",
                  editor: str = "Tyler Toenyes",
                  phone: str = "(314) 267-4194",
                  place: str = "Alton, Illinois",
                  fragment: bool = False) -> str:
    """
    fragment=True returns the inner content only, with no <!DOCTYPE>,
    <html>, <head> or <body>.

    Buttondown wraps whatever you send inside its own template. Posting a
    complete HTML document into a template slot produces nested <html>
    tags, which Outlook in particular renders unpredictably. Send the
    fragment to Buttondown; keep the full document for local preview and
    for any provider that expects a standalone file.
    """
    sigs = sorted(signals, key=lambda s: -s.score)
    total = sum(s.amount for s in sigs if s.amount)
    today = dt.date.today()
    nxt = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
    quiet = len(sigs) < 8

    lede = (f"Every water and wastewater item from municipal council records "
            f"across {territory} and the upper Midwest. The Monday digest is "
            f"free, and stays free.")
    if quiet:
        lede = ("A quiet week. Council calendars run in cycles, and this is "
                "one of the empty ones. We publish it exactly as it came in — "
                "free, and stays free, quiet weeks included.")

    def stat(n, l):
        return (f'<td width="33%" valign="top" style="padding:18px 10px;'
                f'text-align:center;">'
                f'<div style="font:700 26px/1 {SANS};color:{P["ink"]};'
                f'letter-spacing:-.02em;">{n}</div>'
                f'<div style="font:400 15px/1.3 {MONO};letter-spacing:.06em;'
                f'color:{P["secondary"]};padding-top:7px;">{l}</div></td>')

    rows = "".join(_row(s) for s in sigs) or (
        f'<tr><td style="padding:26px 0;font:400 17px/1.5 {SANS};'
        f'color:{P["secondary"]};">No qualifying activity this period.</td></tr>')

    inner = f"""<table role="presentation" width="100%" cellpadding="0"
 cellspacing="0" border="0" style="background:{P['surface']};padding:30px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
 style="width:600px;max-width:100%;background:{P['bg']};">
<tr><td style="padding:28px 28px 34px;">

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="font:700 26px/1.1 {SANS};color:{P['ink']};
    letter-spacing:-.02em;">{territory} Water Signals</td></tr>
  <tr><td style="padding-top:4px;font:400 17px/1.4 {SANS};
    color:{P['secondary']};">Municipal water &amp; wastewater capital
    projects</td></tr>
 </table>

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin:16px 0 22px;border-top:1px solid {P['line']};
  border-bottom:1px solid {P['line']};">
  <tr><td style="padding:9px 0;font:400 15px/1.4 {MONO};letter-spacing:.04em;
   color:{P['secondary']};">LAST BUILD <span style="color:{P['ink']};
   font-weight:600;">{today:%Y-%m-%d} 06:00 CT</span> &nbsp;·&nbsp;
   NEXT BUILD {nxt:%Y-%m-%d}</td></tr>
 </table>

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="font:400 18px/1.5 {SANS};color:{P['body']};">{lede}</td></tr>
  <tr><td style="padding-top:12px;font:600 18px/1.45 {SANS};
   color:{P['design']};">The deal is usually decided before the RFP is
   published.</td></tr>
 </table>

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin:22px 0 6px;border-top:1px solid {P['line-hard']};
  border-bottom:1px solid {P['line']};">
  <tr>{stat(money(total) if total else '—', 'IDENTIFIED')}
      {stat(len(sigs), 'NEW ITEMS')}
      {stat(len({s.city for s in sigs}), 'MUNICIPALITIES')}</tr>
 </table>

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  {rows}
 </table>

 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin-top:26px;">
  <tr><td style="font:400 16px/1.6 {SANS};color:{P['secondary']};">
   Items are drawn from published council and committee records only.
   Nothing here is confidential, and nothing here is a forecast — each
   entry is a document a municipality has already filed, carrying its own
   public record number. Dollar figures are taken from the record itself;
   where a record states no amount, none is shown.
  </td></tr>
  <tr><td style="padding-top:18px;font:400 16px/1.6 {SANS};
   color:{P['secondary']};border-top:1px solid {P['line']};margin-top:18px;">
   <strong style="color:{P['ink']};">{territory} Water Signals</strong><br>
   {editor}, editor · {place}<br>
   <a href="tel:+13142674194" style="color:{P['design']};">{phone}</a><br><br>
   Compiled from public records. Not affiliated with any municipality or
   agency. &nbsp;<a href="{unsubscribe}"
   style="color:{P['secondary']};">Unsubscribe</a>
  </td></tr>
 </table>

</td></tr></table>
</td></tr></table>"""

    if fragment:
        return inner
    return (f'<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{territory} Water Signals</title></head>\n'
            f'<body style="margin:0;padding:0;background:{P["surface"]};">\n'
            f'{inner}\n</body></html>')


def to_plaintext(signals: Iterable, territory: str = "Wisconsin",
                 days: int = 14) -> str:
    """Always send alongside the HTML — materially improves deliverability."""
    sigs = sorted(signals, key=lambda s: -s.score)
    out = [f"{territory.upper()} WATER SIGNALS",
           "Municipal water & wastewater capital projects",
           f"Last build {dt.date.today():%Y-%m-%d} 06:00 CT", "",
           "The deal is usually decided before the RFP is published.", ""]
    for s in sigs:
        _, label, sub, _ = stage_of(s.matched, s.score)
        place, stamp = dateline(s.city, s.intro_date)
        out.append(f"[{label}{' · ' + sub if sub else ''}]")
        out.append(f"  {money(s.amount) if s.amount else 'NO AMOUNT IN RECORD'}")
        out.append(f"  {s.title}")
        out.append(f"  {place} — {stamp} · RECORD {s.file_no} · {s.status}")
        out.append("")
    out += ["Compiled from public records. The Monday digest is free, and "
            "stays free.", "Not affiliated with any municipality or agency."]
    return "\n".join(out)
