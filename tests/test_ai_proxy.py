import base64
import json
import unittest
from unittest.mock import patch

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server import ai_proxy


def make_reply(payload: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class SanitizeTests(unittest.TestCase):
    def test_clamps_out_of_bounds_coords(self):
        raw = [{"label": "X", "reason": "r",
                "bbox": {"x": -0.5, "y": 2.0, "w": 0.9, "h": 0.5}}]
        # y=2.0 clamps to 1.0, leaves no vertical room -> entry rejected
        self.assertEqual(ai_proxy.sanitize_circles(raw), [])

    def test_box_shrunk_to_image(self):
        raw = [{"label": "A", "reason": "r", "bbox": {"x": 0.9, "y": 0.1,
                                                        "w": 0.5, "h": 0.2}}]
        (box,) = ai_proxy.sanitize_circles(raw)
        self.assertAlmostEqual(box["w"], 0.1, places=6)

    def test_garbage_entries_dropped(self):
        raw = [{"label": "", "bbox": {"x": 0, "y": 0, "w": 0.1, "h": 0.1}},
               {"bbox": "not-a-box"},
               "junk",
               {"label": "ok", "reason": "r", "bbox": {"x": "abc"}},
               {"label": "ok2", "reason": "r", "bbox": {"x": 0.5, "y": 0.9,
                                                          "w": 0.2, "h": 0.2}}]
        # garbage dropped; the last (partially out of bounds) entry is kept shrunk
        self.assertEqual(ai_proxy.sanitize_circles(raw),
                         [{"x": 0.5, "y": 0.9, "w": 0.2, "h": 0.1,
                           "label": "ok2", "reason": "r"}])

    def test_max_eight_circles(self):
        raw = [{"label": f"m{i}", "reason": "r",
                "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}
               for i in range(20)]
        self.assertEqual(len(ai_proxy.sanitize_circles(raw)), 8)

    def test_non_list_input(self):
        self.assertEqual(ai_proxy.sanitize_circles({"nope": 1}), [])


class ParseTests(unittest.TestCase):
    def test_plain_json(self):
        out = ai_proxy.parse_model_json(
            '{"observations": [], "verdict": "v", "confidence": "low"}')
        self.assertEqual(out["verdict"], "v")

    def test_code_fence(self):
        text = '```json\n{"observations": [], "verdict": "fenced", "confidence": "medium"}\n```'
        self.assertEqual(ai_proxy.parse_model_json(text)["verdict"], "fenced")

    def test_prose_wrapped(self):
        text = 'Sure! {"observations": [], "verdict": "prose", "confidence": "low"} done.'
        self.assertEqual(ai_proxy.parse_model_json(text)["verdict"], "prose")

    def test_fail_closed(self):
        with self.assertRaises(ai_proxy.ProxyError):
            ai_proxy.parse_model_json("I could not analyze this photo.")

    def test_observations_sanitized(self):
        out = ai_proxy.parse_model_json(
            '{"observations": [{"label": "925", "reason": "r",'
            ' "bbox": {"x": 9, "y": 0, "w": 0.1, "h": 0.1}},'
            ' {"label": "real", "reason": "r",'
            ' "bbox": {"x": 0.2, "y": 0.3, "w": 0.1, "h": 0.1}}],'
            ' "verdict": "v", "confidence": "high"}')
        self.assertEqual([o["label"] for o in out["observations"]], ["real"])


DATA_URL = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()


class AnalyzeTests(unittest.TestCase):
    def test_bad_data_url_rejected(self):
        with self.assertRaises(ai_proxy.ProxyError):
            ai_proxy.analyze_image("https://evil.example/x.png")

    def test_model_coords_never_drawn_locally(self):
        # Proxy returns whatever the (mocked) model said; drawing is app-side.
        calls = []

        def fake_request(url, body, key):
            calls.append((url, body, key))
            return make_reply({
                "observations": [{"label": "EPNS", "reason": "plated",
                                  "bbox": {"x": 0.4, "y": 0.5, "w": 0.1, "h": 0.1}}],
                "verdict": "silver plate", "confidence": "high"})

        with patch.object(ai_proxy, "load_dev_config",
                          return_value={"base_url": "http://127.0.0.1:9",
                                        "api_key": "test-key"}):
            out = ai_proxy.analyze_image(DATA_URL, "spoon", request_fn=fake_request)
        self.assertEqual(out["observations"][0]["label"], "EPNS")
        self.assertEqual(out["verdict"], "silver plate")
        url, body, key = calls[0]
        self.assertTrue(url.endswith("/v1/chat/completions"))
        self.assertEqual(key, "test-key")
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_missing_content_fails(self):
        def fake_request(url, body, key):
            return {"choices": []}

        with patch.object(ai_proxy, "load_dev_config",
                          return_value={"base_url": "http://127.0.0.1:9",
                                        "api_key": "test-key"}):
            with self.assertRaises(ai_proxy.ProxyError):
                ai_proxy.analyze_image(DATA_URL, request_fn=fake_request)


if __name__ == "__main__":
    unittest.main()
