"""Refresh the public silver price feed for the GitHub Pages deployment.

Runs in CI (GitHub Actions) where outbound HTTPS works without CORS limits.
Writes public/feeds/silver_prices.json next to the rest of the deploy; the
workflow then copies it to the gh-pages branch. The PWA fetches it from the
same origin (https://<user>.github.io/EstateScout/feeds/silver_prices.json),
which is why this exists: the browser can call Yahoo only from a server.

Feeds (verified in price_service):
  - Western:  Yahoo Finance SI=F (COMEX futures, delayed)
  - FX:       Yahoo Finance CNY=X
  - Shanghai: SGE Ag(T+D) delayed quotation, CNY/kg -> CNY/g
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import price_service  # noqa: E402

FEED_FILE = REPO_ROOT / "public" / "feeds" / "silver_prices.json"


def build_feed() -> dict:
    western = usd_cny = None
    western_source = "Yahoo Finance SI=F (COMEX futures, delayed)"
    status = "delayed"
    try:
        western, usd_cny = price_service._yahoo_comex(price_service._get_json)
    except Exception:
        status = "partial"
        western_source = "Yahoo Finance (unavailable)"

    shanghai_g = None
    shanghai_source = "Shanghai Gold Exchange Ag(T+D), delayed quotation"
    if western is not None:
        try:
            shanghai_g = price_service._sge_ag_td(price_service._get)
        except Exception:
            status = "partial"
            shanghai_source = "Shanghai Gold Exchange (unavailable)"

    feed: dict = {
        "western_usd_per_troy_oz": western,
        "usd_cny": usd_cny,
        "western_source": western_source,
        "shanghai_source": shanghai_source,
        "fetched_at": int(time.time()),
        "status": status,
        "deployment": "github-pages",
    }
    if shanghai_g is not None and usd_cny:
        feed["shanghai_cny_per_gram"] = shanghai_g
        feed["shanghai_usd_per_troy_oz"] = price_service.shanghai_usd_per_oz(shanghai_g, usd_cny)
    return feed


def main() -> int:
    feed = build_feed()
    FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if FEED_FILE.exists():
        try:
            previous = json.loads(FEED_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
    FEED_FILE.write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(feed, indent=2))
    if previous == feed:
        print("feed unchanged since last run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())