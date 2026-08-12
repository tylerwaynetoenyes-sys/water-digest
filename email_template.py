#!/usr/bin/env python3
"""
Email rendering for the water/wastewater digest.

Built for Outlook, not for looks. Municipal reps read email in Outlook
on a work laptop, so: table layout, inline styles, no images, no
web fonts, 600px max. Anything fancier renders as garbage for exactly
the people you're trying to sell to.

    from email_template import to_email_html
    html = to_email_html(signals, territory="Wisconsin", days=30)
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

INK = "#1a2733"
MUTED = "#5f7183"
LINE = "#dde4ea"
ACCENT = "#0f5c6b"
HOT = "#a4442c"
BG = "#f2f5f7"
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
        "'Helvetica Neue',Arial,sans-serif")


def _tier(score: int) -> tuple[str, str]:
    if score >= 20:
        return "HIGH", HOT
    if score >= 12:
        return "NOTABLE", ACCENT
    return "TRACKING", MUTED


def _row(sig) -> str:
    label, color = _tier(sig.score)
    amount = (
        f'<div style="font:600 17px/1.3 {FONT};color:{INK};padding-top:6px;">'
        f'${sig.amount:,.0f}</div>' if sig.amount else ""
    )
    return f"""
<tr><td style="padding:0 0 14px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#ffffff;border:1px solid {LINE};border-radius:6px;">
    <tr><td style="padding:16px 18px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font:700 10px/1 {FONT};letter-spacing:.09em;
                     color:{color};text-transform:uppercase;">{label}</td>
          <td align="right" style="font:400 11px/1 {FONT};color:{MUTED};">
            {sig.intro_date}</td>
        </tr>
      </table>
      <div style="font:700 13px/1.3 {FONT};color:{ACCENT};padding-top:10px;">
        {sig.city}</div>
      <div style="font:400 14px/1.5 {FONT};color:{INK};padding-top:5px;">
        {sig.title}</div>
      {amount}
      <div style="font:400 11px/1.4 {FONT};color:{MUTED};padding-top:10px;
                  border-top:1px solid {LINE};margin-top:12px;">
        File {sig.file_no} &middot; {sig.matter_type} &middot; {sig.status}
      </div>
    </td></tr>
  </table>
</td></tr>"""


def to_email_html(
    signals: Iterable,
    territory: str = "Wisconsin",
    days: int = 30,
    unsubscribe: str = "#",
) -> str:
    sigs = sorted(signals, key=lambda s: -s.score)
    money = sum(s.amount for s in sigs if s.amount)
    cities = len({s.city for s in sigs})
    today = dt.date.today()

    stat = (f"{len(sigs)} items &middot; {cities} municipalities"
            + (f" &middot; ${money:,.0f} identified" if money else ""))

    rows = "".join(_row(s) for s in sigs) or (
        f'<tr><td style="font:400 14px/1.5 {FONT};color:{MUTED};'
        f'padding:24px;background:#fff;border:1px solid {LINE};'
        f'border-radius:6px;">No qualifying activity this period.</td></tr>'
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{territory} Water Signals</title></head>
<body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:{BG};padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="width:600px;max-width:100%;">

  <tr><td style="padding-bottom:20px;border-bottom:2px solid {INK};">
    <div style="font:700 19px/1.2 {FONT};color:{INK};">
      {territory} Water &amp; Wastewater Signals</div>
    <div style="font:400 13px/1.5 {FONT};color:{MUTED};padding-top:6px;">
      Council and committee activity, last {days} days &middot;
      {today:%B %-d, %Y}</div>
  </td></tr>

  <tr><td style="padding:14px 0 20px 0;">
    <div style="font:600 12px/1.4 {FONT};color:{ACCENT};
                letter-spacing:.03em;">{stat}</div>
  </td></tr>

  {rows}

  <tr><td style="padding-top:14px;border-top:1px solid {LINE};">
    <div style="font:400 11px/1.6 {FONT};color:{MUTED};">
      Compiled from public council agendas and legislative records via the
      Legistar public API. Every item links to a public record you can
      verify. Coverage list available on request &mdash; we publish exactly
      which municipalities we track and which we don't.
    </div>
    <div style="font:400 11px/1.6 {FONT};color:{MUTED};padding-top:10px;">
      <a href="{unsubscribe}" style="color:{MUTED};">Unsubscribe</a>
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def to_plaintext(signals: Iterable, territory: str = "Wisconsin",
                 days: int = 30) -> str:
    """Always send a plaintext alternative. Improves deliverability."""
    sigs = sorted(signals, key=lambda s: -s.score)
    out = [f"{territory.upper()} WATER & WASTEWATER SIGNALS",
           f"Council activity, last {days} days", ""]
    for s in sigs:
        label, _ = _tier(s.score)
        out.append(f"[{label}] {s.city} — {s.intro_date}")
        out.append(f"  {s.title}")
        if s.amount:
            out.append(f"  ${s.amount:,.0f}")
        out.append(f"  File {s.file_no} · {s.matter_type} · {s.status}")
        out.append("")
    out.append("Source: public council records via the Legistar public API.")
    return "\n".join(out)
