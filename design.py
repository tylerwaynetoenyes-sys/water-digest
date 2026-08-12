"""
Design tokens for Wisconsin Water Signals.

Extracted from the approved Claude Design revision (rev 4) and verified:
every text colour meets WCAG AA against its own background in both
light and dark. Nothing below 15px. Stage chips carry a shape channel
as well as a colour channel, so they survive greyscale and colour
blindness — PLANNING and DESIGN measured only 20 units apart under
deuteranopia, which filled-vs-outlined resolves.

This module is the single source of truth. The page, the email and any
future surface read from here.
"""

# ---------------------------------------------------------------------------
# Palettes. Verified contrast in comments — ratio against that mode's surface.
# ---------------------------------------------------------------------------
LIGHT = {
    "bg":        "#ffffff",
    "surface":   "#f7f8f9",
    "ink":       "#17191c",   # 17.61:1
    "body":      "#2c3138",   # 13.10:1
    "secondary": "#565d68",   # 6.64:1
    "line":      "rgba(23,25,28,.09)",
    "line-soft": "rgba(23,25,28,.07)",
    "line-hard": "rgba(23,25,28,.22)",
    "planning":  "#33456b",   # 9.53:1
    "design":    "#1f5a66",   # 7.74:1
    "bidding":   "#8a4b1f",   # 6.76:1
    "on-fill":   "#ffffff",
}

DARK = {
    "bg":        "#0e1113",
    "surface":   "#171b1e",
    "ink":       "#e8ebee",   # 14.48:1
    "body":      "#c6ced6",   # 10.89:1
    "secondary": "#9aa4af",   # 6.85:1
    "line":      "rgba(255,255,255,.11)",
    "line-soft": "rgba(255,255,255,.08)",
    "line-hard": "rgba(255,255,255,.24)",
    "planning":  "#8fa8d8",   # 7.23:1
    "design":    "#79b8c4",   # 7.81:1
    "bidding":   "#d99a72",   # 7.27:1
    "on-fill":   "#0e1113",
}

SANS = "-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = ("ui-monospace,'Cascadia Mono',Consolas,'Segoe UI Mono',"
        "'Liberation Mono',monospace")

# 15px is the floor. Readers skew 45-65; presbyopia is the baseline case.
MIN_SIZE = 15

# ---------------------------------------------------------------------------
# Buying-cycle stage. A product decision, not a visual one: a raw score
# means nothing to a rep, but "Planning · 2+ years out" tells them what to
# do this week. Chip shape is the accessibility channel.
# ---------------------------------------------------------------------------
PLANNING = ("intent to apply", "priority evaluation", "master plan",
            "facility plan", "capital improvement plan", "loan")
DESIGN_KW = ("engineering services", "professional services", "feasibility",
             "preliminary design", "study")
BIDDING = ("bid opening", "bids received", "awarding", "award of contract",
           "notice to bidders", "request for proposals", "change order")

# key → (label, sublabel, chip style)
STAGES = {
    "planning": ("PLANNING", "2+ years out",   "filled"),
    "design":   ("DESIGN",   "6–18 months out", "outlined"),
    "bidding":  ("BIDDING",  "Active now",      "filled"),
    "tracking": ("TRACKING", "",                "outlined"),
}


def stage_of(matched, score: int) -> tuple[str, str, str, str]:
    """→ (key, label, sublabel, chip_style)"""
    m = {k.lower() for k in matched}
    if m & set(PLANNING):
        key = "planning"
    elif m & set(DESIGN_KW):
        key = "design"
    elif m & set(BIDDING):
        key = "bidding"
    else:
        key = "tracking"
    return (key, *STAGES[key])


# ---------------------------------------------------------------------------
def money(v: float, compact: bool = False) -> str:
    """Exact by default — an exact figure is checkable, and checkable is
    the whole trust argument. Compact only where space forces it."""
    if not compact:
        return f"${v:,.0f}"
    if v >= 1_000_000_000:
        return f"${v/1e9:.2f}B".replace(".00B", "B")
    if v >= 1_000_000:
        return f"${v/1e6:.2f}M".replace(".00M", "M")
    return f"${v:,.0f}"


AP_STATE = {
    "WI": "Wis.", "MN": "Minn.", "IL": "Ill.", "IA": "Iowa", "MI": "Mich.",
    "OH": "Ohio", "IN": "Ind.", "MO": "Mo.", "CO": "Colo.", "CA": "Calif.",
    "WA": "Wash.", "TX": "Texas", "NY": "N.Y.", "PA": "Pa.",
}

MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July",
          "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def dateline(city: str, iso_date: str) -> tuple[str, str]:
    """('RACINE, WIS.', 'AUG. 10') — AP style, journalism convention.
    Reads as sourced rather than dumped."""
    if "," in city:
        name, st = [p.strip() for p in city.rsplit(",", 1)]
    else:
        name, st = city, ""
    place = f"{name}, {AP_STATE.get(st, st)}".strip(", ").upper()
    try:
        y, m, d = iso_date.split("-")
        stamp = f"{MONTHS[int(m)-1]} {int(d)}".upper()
    except Exception:  # noqa: BLE001
        stamp = iso_date
    return place, stamp


def css_vars(p: dict) -> str:
    return "".join(f"--{k}:{v};" for k, v in p.items())
