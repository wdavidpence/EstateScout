"""Verified silver-market feeds, conversion, and five-minute disk caching."""
from __future__ import annotations

import datetime
import html
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TROY_OZ_GRAMS = 31.1034768
CACHE_TTL_SECONDS = 5 * 60
DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "silver_prices.json"
SGE_DELAYED_URL = "https://www.sge.com.cn/sjzx/yshqbg"
SGE_DAILY_URL = "https://www.sge.com.cn/sjzx/quotation_daily_new"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1d&interval=1m"


def shanghai_usd_per_oz(cny_per_gram: float, usd_cny: float) -> float:
    if cny_per_gram < 0 or usd_cny <= 0:
        raise ValueError("prices must be non-negative and USD/CNY must be positive")
    return cny_per_gram * TROY_OZ_GRAMS / usd_cny


def _get(url: str, timeout: float = 10.0) -> bytes:
    request = Request(url, headers={"User-Agent": "EstateScout/1.0 (+silver research)"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310: configured HTTPS feeds
        return response.read()


def _get_json(url: str, timeout: float = 10.0) -> Any:
    return json.loads(_get(url, timeout).decode("utf-8"))


def _extract_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        raise ValueError(f"not numeric: {value!r}")
    return float(match.group())


def _metals_api(fetch_json: Callable[[str], Any]) -> tuple[float, float] | None:
    key = os.getenv("ESTATESCOUT_METALS_API_KEY", "")
    if not key:
        return None  # No API key configured — caller should use cached or unavailable
    query = urlencode({"access_key": key, "base": "USD", "symbols": "XAG,CNY"})
    data = fetch_json("https://metals-api.com/api/latest?" + query)
    rates = data.get("rates", {})
    western = rates.get("XAG") or rates.get("Silver(USDXAG)")
    usd_cny = rates.get("CNY")
    if western is None or usd_cny is None:
        raise KeyError("Metals-API response did not include XAG and CNY")
    # Rates are USD per troy oz for the silver symbol and USD/CNY for FX.
    return _extract_number(western), _extract_number(usd_cny)


def _yahoo_chart_price(symbol: str, fetch_json: Callable[[str], Any]) -> float:
    """Return Yahoo Finance's delayed regular-market price for a symbol."""
    data = fetch_json(YAHOO_CHART_URL.format(symbol))
    result = data.get("chart", {}).get("result", [])
    if not result or not isinstance(result[0], dict):
        raise ValueError(f"Yahoo Finance returned no chart data for {symbol}")
    meta = result[0].get("meta", {})
    value = meta.get("regularMarketPrice", meta.get("previousClose"))
    price = _extract_number(value)
    if price <= 0:
        raise ValueError(f"Yahoo Finance returned an invalid price for {symbol}")
    return price


def _yahoo_comex(fetch_json: Callable[[str], Any]) -> tuple[float, float]:
    """Get delayed COMEX silver futures and USD/CNY from Yahoo Finance."""
    return _yahoo_chart_price("SI=F", fetch_json), _yahoo_chart_price("CNY=X", fetch_json)


def _parse_sge_ag_rows(body: str) -> list[float]:
    """All positive CNY/kg quotes found on an SGE page for the Ag(T+D) contract.

    Rows list the contract name followed by numeric cells; the first cell after
    the name is the latest quote. Zero/blank cells mean 'no quote' (market
    closed or stale static page) and are skipped, never treated as a price.
    """
    quotes = []
    for match in re.finditer(r"Ag\s*\(\s*T\+D\s*\)", body, re.I):
        row = body[match.end():]
        row = row.split("</tr>", 1)[0]
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.I | re.S)
        if not cells:
            continue
        try:
            value = _extract_number(cells[0])
        except ValueError:
            continue
        if value > 0:
            quotes.append(value / 1000.0)
    return quotes


def _sge_ag_td(fetch_bytes: Callable[[str], bytes]) -> tuple[float, str]:
    """Latest official SGE Ag(T+D) quote as (CNY per gram, source label).

    Tries the delayed intraday page first; its static table renders 0.0 placeholders
    outside market hours, so we fall back to the daily quotation pages over a recent
    window and keep the highest positive quote found (latest trading day).
    """
    try:
        delayed = _parse_sge_ag_rows(
            html.unescape(fetch_bytes(SGE_DELAYED_URL).decode("utf-8", errors="replace"))
        )
        if delayed:
            return max(delayed), "Shanghai Gold Exchange Ag(T+D), delayed quotation"
    except (URLError, TimeoutError, OSError):
        pass
    window = [datetime.date.today() - datetime.timedelta(days=day) for day in range(10)]
    daily: list[float] = []
    for day in window:
        url = f"{SGE_DAILY_URL}?start_date={day.isoformat()}&end_date={day.isoformat()}"
        try:
            daily.extend(
                _parse_sge_ag_rows(html.unescape(fetch_bytes(url).decode("utf-8", errors="replace")))
            )
        except (URLError, TimeoutError, OSError):
            continue
        if daily:
            break
    if not daily:
        raise ValueError("no positive Ag(T+D) quote on official SGE pages")
    return max(daily), "Shanghai Gold Exchange Ag(T+D), daily quotation"


def _fetch_live(fetch_json: Callable[[str], Any] = _get_json, fetch_bytes: Callable[[str], bytes] = _get) -> dict[str, Any]:
    metals = _metals_api(fetch_json)
    if metals is not None:
        western_usd_oz, usd_cny = metals
        western_source = "Metals-API"
        status = "live"
    else:
        western_usd_oz, usd_cny = _yahoo_comex(fetch_json)
        western_source = "Yahoo Finance SI=F (COMEX futures, delayed)"
        status = "delayed"
    try:
        shanghai_cny_g, shanghai_source = _sge_ag_td(fetch_bytes)
    except (ValueError, URLError, TimeoutError, OSError):
        return {
            "western_usd_per_troy_oz": western_usd_oz,
            "usd_cny": usd_cny,
            "western_source": western_source,
            "shanghai_source": "Shanghai Gold Exchange (unavailable)",
            "fetched_at": int(time.time()),
            "status": "partial",
        }
    shanghai_usd_oz = shanghai_usd_per_oz(shanghai_cny_g, usd_cny)
    now = int(time.time())
    return {
        "western_usd_per_troy_oz": western_usd_oz,
        "shanghai_cny_per_gram": shanghai_cny_g,
        "usd_cny": usd_cny,
        "shanghai_usd_per_troy_oz": shanghai_usd_oz,
        "western_source": western_source,
        "shanghai_source": shanghai_source,
        "fetched_at": now,
        "status": status,
    }


def _load_cache() -> dict[str, Any] | None:
    try:
        with CACHE_FILE.open(encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def get_prices(force_refresh: bool = False, fetcher: Callable[[str], Any] = _get_json) -> dict[str, Any]:
    cached = _load_cache()
    now = int(time.time())
    if cached and not force_refresh and now - int(cached.get("fetched_at", 0)) < CACHE_TTL_SECONDS:
        return {**cached, "status": "cached"}
    try:
        live = _fetch_live(fetcher, _get)
        if live is not None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
            return live
        # No live data available (no API key or all feeds down)
        if cached:
            return {**cached, "status": "stale", "error": "No API key configured or all price feeds unavailable"}
        return {"status": "unavailable", "error": "No API key configured and no cached data available.", "fetched_at": now}
    except (OSError, URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if cached:
            return {**cached, "status": "stale", "error": str(exc)}
        return {"status": "unavailable", "error": str(exc), "fetched_at": now}


def format_prices(prices: dict[str, Any]) -> str:
    status = prices.get("status", "unknown").upper()
    if status == "UNAVAILABLE":
        return "🥈 *Silver Prices Unavailable*\n\nNo verified price feed is available right now. Try again later."
    # Handle partial status (western only, no Shanghai)
    if status == "PARTIAL":
        western = prices.get("western_usd_per_troy_oz")
        usd_cny = prices.get("usd_cny")
        if western is not None and usd_cny is not None:
            return (
                f"🥈 *Silver Prices* — `{status}`\n\n"
                f"🌎 Western spot: *${float(western):,.2f} USD / troy oz*\n"
                f"🇨🇳 Shanghai: *unavailable*\n"
                f"🇨🇳 Shanghai converted: *unavailable*\n\n"
                f"FX: 1 USD = ¥{float(usd_cny):,.4f} CNY\n"
                f"Sources: {prices.get('western_source', 'Western feed')}; {prices.get('shanghai_source', 'Shanghai feed')}\n"
                f"Feed timestamp: `{prices.get('fetched_at', 'unknown')}`"
            )
    return (
        f"🥈 *Silver Prices* — `{status}`\n\n"
        f"🌎 Western spot: *${float(prices['western_usd_per_troy_oz']):,.2f} USD / troy oz*\n"
        f"🇨🇳 Shanghai: *¥{float(prices['shanghai_cny_per_gram']):,.2f} CNY / gram*\n"
        f"🇨🇳 Shanghai converted: *${float(prices['shanghai_usd_per_troy_oz']):,.2f} USD / troy oz*\n\n"
        f"FX: 1 USD = ¥{float(prices['usd_cny']):,.4f} CNY\n"
        f"Conversion: {TROY_OZ_GRAMS} grams = 1 troy oz\n"
        f"Sources: {prices.get('western_source', 'Western feed')}; {prices.get('shanghai_source', 'Shanghai feed')}\n"
        f"Feed timestamp: `{prices.get('fetched_at', 'unknown')}`"
    )
