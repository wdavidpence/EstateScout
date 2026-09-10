import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import price_service


class PriceServiceTests(unittest.TestCase):
    def test_shanghai_conversion(self):
        self.assertEqual(price_service.shanghai_usd_per_oz(30.0, 7.5), 124.4139072)

    def test_format_contains_all_requested_units(self):
        text = price_service.format_prices({
            "status": "live",
            "western_usd_per_troy_oz": 35.25,
            "shanghai_cny_per_gram": 8.5,
            "shanghai_usd_per_troy_oz": 35.25,
            "usd_cny": 7.5,
            "fetched_at": 123,
        })
        self.assertIn("USD / troy oz", text)
        self.assertIn("CNY / gram", text)
        self.assertIn("Shanghai converted", text)
        self.assertIn("31.1034768", text)

    def test_yahoo_fallback_provides_delayed_comex_and_shanghai_conversion(self):
        def fetch_json(url):
            if "SI=F" in url:
                return {"chart": {"result": [{"meta": {"regularMarketPrice": 35.25}}]}}
            if "CNY=X" in url:
                return {"chart": {"result": [{"meta": {"regularMarketPrice": 7.5}}]}}
            self.fail(f"Unexpected URL: {url}")

        def fetch_bytes(_url):
            return b"<tr><td>Ag(T+D)</td><td>8,500.00</td></tr>"

        with patch.dict("os.environ", {"ESTATESCOUT_METALS_API_KEY": ""}, clear=False):
            result = price_service._fetch_live(fetch_json, fetch_bytes)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "delayed")
        self.assertEqual(result["western_usd_per_troy_oz"], 35.25)
        self.assertEqual(result["shanghai_cny_per_gram"], 8.5)
        self.assertIn("Yahoo Finance SI=F", result["western_source"])

    def test_sge_parser_handles_span_wrapped_price(self):
        # SGE wraps the latest price in <span class="colorRed/colorGreen"> tags.
        body = (
            b'<tr class=" border_ea noTop_border">\n'
            b'  <td align="center" height="40">Ag(T+D)</td>\n'
            b'  <td align="center"><span class="colorGreen">15748.0</span></td>\n'
            b'  <td align="center" class="colorGreen">16000.0</td>\n'
            b'  <td align="center" class="colorGreen">15580.0</td>\n'
            b'</tr>'
        )
        self.assertAlmostEqual(price_service._sge_ag_td(lambda _url: body), 15.748, places=6)

    def test_sge_parser_rejects_zero_quote(self):
        body = b'<tr><td>Ag(T+D)</td><td>0.0</td></tr>'
        with self.assertRaises(ValueError):
            price_service._sge_ag_td(lambda _url: body)

    def test_cache_is_used(self):
        cache = Path(self.id().replace(".", "_") + ".json")
        try:
            cache.write_text(json.dumps({
                "status": "live",
                "western_usd_per_troy_oz": 30,
                "shanghai_cny_per_gram": 7,
                "shanghai_usd_per_troy_oz": 29,
                "usd_cny": 7.5,
                "fetched_at": int(time.time()),
            }))
            with patch.object(price_service, "CACHE_FILE", cache), patch.object(price_service, "DATA_DIR", cache.parent):
                result = price_service.get_prices(fetcher=lambda _: self.fail("network should not be called"))
            self.assertEqual(result["status"], "cached")
            self.assertEqual(result["western_usd_per_troy_oz"], 30)
        finally:
            cache.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
