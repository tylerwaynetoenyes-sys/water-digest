# Water Digest

Pulls water & wastewater items out of municipal council agendas,
scores them for procurement relevance, emails a digest, and publishes
a public tracker page.

## Files

| File | What it does |
|---|---|
| `legistar_digest.py` | Fetches council records + scores them. The keyword weights near the top are the actual product — tune them. |
| `ops.py` | Dedup, silent-failure detection, coverage checking |
| `email_template.py` | Renders the digest as Outlook-safe HTML email |
| `build_site.py` | Renders the public tracker page |
| `wi_candidates.txt` | Candidate city codes to test |
| `.github/workflows/coverage.yml` | Button: test which cities are reachable |
| `.github/workflows/digest.yml` | Timer: runs every Monday |

## Setup

See CHECKLIST.md (sent separately).

## Data source

Legistar public API — free, unauthenticated, public records.
No account, no terms of service accepted, no scraping.
