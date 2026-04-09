"""
Scrape Google Scholar profile for h-index, i10-index, and citation count.
Generate shields.io-style SVG badges.

Methods (tried in order):
  1. `scholarly` library (handles anti-bot, retries)
  2. Manual requests + BeautifulSoup fallback

Usage:
  SCHOLAR_USER_ID=HMfqWHsAAAAJ python scripts/update_scholar_badges.py

Outputs:
  figs/scholar_badges/citations.svg
  figs/scholar_badges/h_index.svg
  figs/scholar_badges/i10_index.svg
  figs/scholar_badges/stats.json
"""

import json
import os
import sys
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
SCHOLAR_USER_ID = os.environ.get("SCHOLAR_USER_ID", "")
BADGE_OUTPUT_DIR = Path(os.environ.get("BADGE_OUTPUT_DIR", "figs/scholar_badges"))
# ────────────────────────────────────────────────────────────────────────────


def fetch_with_scholarly(user_id: str) -> dict:
    """Fallback method: use the scholarly library."""
    from scholarly import scholarly
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("scholarly timed out after 60 seconds")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(60)  # 60 second timeout

    try:
        print("  [scholarly] Looking up author...")
        author = scholarly.search_author_id(user_id)

        if not author:
            raise ValueError(f"No author found for ID: {user_id}")

        author = scholarly.fill(author, sections=["indices"])

        citedby = author.get("citedby", 0)
        h_index = author.get("hindex", 0)
        i10_index = author.get("i10index", 0)

        return {
            "citations": citedby,
            "h_index": h_index,
            "i10_index": i10_index,
        }
    finally:
        signal.alarm(0)  # cancel timeout


def fetch_with_requests(user_id: str) -> dict:
    """Fallback method: manual scrape with requests + BeautifulSoup."""
    import requests
    from bs4 import BeautifulSoup

    url = f"https://scholar.google.com/citations?user={user_id}&hl=en"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    print("  [requests] Fetching Scholar profile page...")
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    if "Please show you" in resp.text or "CAPTCHA" in resp.text.upper():
        raise RuntimeError("Google returned a CAPTCHA page. Try the scholarly method or use a proxy.")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Stats table: id="gsc_rsb_st"
    table = soup.find("table", id="gsc_rsb_st")
    if not table:
        snippet = resp.text[:1000].replace("\n", " ")
        raise RuntimeError(
            f"Could not find stats table (id='gsc_rsb_st'). "
            f"Page may have changed or returned an error. Snippet: {snippet}"
        )

    rows = table.find_all("tr")
    stats = {}
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value_all = cells[1].get_text(strip=True)
            try:
                val = int(value_all)
            except ValueError:
                continue
            if "citation" in label:
                stats["citations"] = val
            elif "h-index" in label:
                stats["h_index"] = val
            elif "i10" in label:
                stats["i10_index"] = val

    if not stats:
        raise RuntimeError("Parsed table but extracted no stats. HTML structure may have changed.")

    return stats


def fetch_scholar_stats(user_id: str) -> dict:
    """Try requests first (fast), fall back to scholarly (slow but robust)."""
    errors = []

    # Method 1: requests + bs4 (fast)
    try:
        print("Method 1: requests + BeautifulSoup")
        return fetch_with_requests(user_id)
    except Exception as e:
        errors.append(f"requests: {e}")
        print(f"  ✗ Failed: {e}")

    # Method 2: scholarly (slower, but handles anti-bot better)
    try:
        print("Method 2: scholarly library (this may take a minute...)")
        return fetch_with_scholarly(user_id)
    except Exception as e:
        errors.append(f"scholarly: {e}")
        print(f"  ✗ Failed: {e}")

    # Both failed
    print("\n═══ ALL METHODS FAILED ═══")
    for err in errors:
        print(f"  • {err}")
    print("\nTroubleshooting:")
    print("  1. Check SCHOLAR_USER_ID is correct (the ?user=XXXX part of your profile URL)")
    print("  2. Google may be rate-limiting — try again later")
    print("  3. Your profile may be private — make it public in Google Scholar settings")
    sys.exit(1)


def generate_shield_svg(label: str, value: str, color: str, filename: str, output_dir: Path):
    """Generate a shields.io-style SVG badge."""
    label_width = len(label) * 6.8 + 10
    value_width = len(value) * 7.5 + 10
    total_width = label_width + value_width

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_width/2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width/2}" y="14" fill="#fff">{label}</text>
    <text aria-hidden="true" x="{label_width + value_width/2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width/2}" y="14" fill="#fff">{value}</text>
  </g>
</svg>"""

    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    filepath.write_text(svg)
    print(f"  ✓ {filepath}")


def main():
    if not SCHOLAR_USER_ID or SCHOLAR_USER_ID == "YOUR_SCHOLAR_ID_HERE":
        print("ERROR: SCHOLAR_USER_ID not set.")
        print("Set it as an environment variable or GitHub Actions secret.")
        print("  export SCHOLAR_USER_ID=HMfqWHsAAAAJ")
        sys.exit(1)

    print(f"Scholar User ID: {SCHOLAR_USER_ID}")
    print(f"Output dir: {BADGE_OUTPUT_DIR}\n")

    stats = fetch_scholar_stats(SCHOLAR_USER_ID)

    print(f"\n✓ Stats retrieved:")
    print(f"  Citations : {stats.get('citations', 'N/A')}")
    print(f"  h-index   : {stats.get('h_index', 'N/A')}")
    print(f"  i10-index : {stats.get('i10_index', 'N/A')}")

    print(f"\nGenerating SVG badges...")
    badge_config = [
        ("citations", str(stats.get("citations", "?")), "#4285F4", "citations.svg"),
        ("h-index", str(stats.get("h_index", "?")), "#0a9396", "h_index.svg"),
        ("i10-index", str(stats.get("i10_index", "?")), "#ee9b00", "i10_index.svg"),
    ]

    for label, value, color, filename in badge_config:
        generate_shield_svg(label, value, color, filename, BADGE_OUTPUT_DIR)

    # JSON summary for debugging
    summary = {**stats, "scholar_user_id": SCHOLAR_USER_ID}
    summary_path = BADGE_OUTPUT_DIR / "stats.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"  ✓ {summary_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
