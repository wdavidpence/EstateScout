"""EstateScout local AI proxy — oMLX (or any OpenAI-compatible) endpoint.

Design contract (do not break):
  - The model NEVER draws and NEVER supplies executable behavior. It only
    returns {observations, circles} with relative coordinates; the app draws
    red circles with fixed local code from the model-supplied coords.
  - Coordinates are validated/clamped server-side to [0,1] and bounded to a
    maximum of 8 circles before the app ever sees them.
  - The oMLX API key is read from ~/.omlx/settings.json at runtime and is
    never logged, returned to the client, or committed.

Proxy API (served by server.py):
  POST /api/analyze  {image: dataURL, note?: string}  ->  AnalysisResult
  GET  /api/health   ->  {ok, model, error?}
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

OMLX_SETTINGS = Path.home() / ".omlx" / "settings.json"
MAX_CIRCLES = 8

SYSTEM_PROMPT = """You are EstateScout, an estate-auction assistant for silver, \
coins, jewelry and collectibles. You will receive one photo taken at an estate \
sale, possibly with an owner note.

Identify: (1) metal/purity hallmarks (925, 800, 835, EPNS, A1, 1800, 750, 585, \
GP, HGP etc.), (2) maker or mint marks, (3) plating or red flags (wearing to \
base metal, worn-through silver plate, casting seams that fake a hallmark), \
(4) what the item most likely is and rough era.

Respond with STRICT JSON only, no prose outside the JSON object, matching:
{
  "observations": [{"label": "short mark or finding",
                    "reason": "one sentence, plain English",
                    "bbox": {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}}],
  "verdict": "one-paragraph assessment for the buyer",
  "confidence": "high" | "medium" | "low"
}
bbox values are RELATIVE to the image (0..1): x,y = top-left of a box that \
encloses the mark. Put a box tightly around each mark you can actually see. \
If no mark is visible, return an empty observations list and say so in verdict. \
Never invent marks you cannot see in the photo.
"""


class ProxyError(RuntimeError):
    pass


def load_omlx_config(path: Path = OMLX_SETTINGS) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    host = data.get("server", {}).get("host", "127.0.0.1")
    port = data.get("server", {}).get("port", 8000)
    key = data.get("auth", {}).get("api_key", "")
    if not key:
        raise ProxyError("no api key in oMLX settings")
    base = "http://127.0.0.1:%s" % port if host in ("0.0.0.0", "::", "*") \
        else "http://%s:%s" % (host, port)
    return {"base_url": base, "api_key": key}


def _clip(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return min(max(number, 0.0), 1.0)


def sanitize_circles(raw: list[Any]) -> list[dict[str, float]]:
    """Keep only well-formed boxes, clamped to image bounds, max MAX_CIRCLES."""
    circles = []
    if not isinstance(raw, list):
        return circles
    for item in raw:
        if not isinstance(item, dict):
            continue
        box = item.get("bbox")
        if not isinstance(box, dict):
            continue
        x, y = _clip(box.get("x")), _clip(box.get("y"))
        w, h = _clip(box.get("w")), _clip(box.get("h"))
        if x is None or y is None or w is None or h is None:
            continue
        if w <= 0 or h <= 0:
            continue
        if x + w > 1.0:
            w = round(1.0 - x, 6)
        if y + h > 1.0:
            h = round(1.0 - y, 6)
        if w <= 0 or h <= 0:
            continue
        label = str(item.get("label", ""))[:60]
        reason = str(item.get("reason", ""))[:240]
        if not label:
            continue
        circles.append({"x": x, "y": y, "w": w, "h": h, "label": label,
                        "reason": reason})
        if len(circles) >= MAX_CIRCLES:
            break
    return circles


def parse_model_json(text: str) -> dict[str, Any]:
    """Parse the model reply into {observations, verdict, confidence}.

    Tolerates code fences and surrounding prose; the payload itself must be
    valid JSON or this raises ProxyError (fail closed — never guess).
    """
    candidates = [text]
    fence = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = fence + candidates
    brace = re.search(r"\{.*\}", text, re.S)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and "observations" in data:
            data["observations"] = sanitize_circles(data.get("observations"))
            data.setdefault("verdict", "No assessment produced.")
            data.setdefault("confidence", "low")
            return data
    raise ProxyError("model reply was not valid JSON")


def default_request(url: str, body: dict[str, Any], api_key: str) -> dict[str, Any]:
    req = Request(url, data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json",
                           "Authorization": "Bearer " + api_key})
    with urlopen(req, timeout=120) as resp:  # nosec: configured local endpoint
        return json.loads(resp.read())


def analyze_image(data_url: str, note: str = "",
                  model: str = "Qwen3.8-Flash-Next-oQ4e-mtp",
                  request_fn=default_request,
                  ) -> dict[str, Any]:
    """Send one image (+optional note) to the local model; return sanitized result."""
    match = re.match(r"data:(image/[a-z+]+);base64,([A-Za-z0-9+/=]+)$", data_url)
    if not match:
        raise ProxyError("image must be a base64 data URL")
    media_type, b64 = match.group(1), match.group(2)
    if len(b64) > 8 * 1024 * 1024:
        raise ProxyError("image too large (max ~6 MB)")

    user_content = [{"type": "image_url",
                     "image_url": {"url": "data:%s;base64,%s" % (media_type, b64)}}]
    user_content.append({"type": "text",
                         "text": ("Owner note: " + note) if note else
                                 "Identify marks and material in this photo."})
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    cfg = load_omlx_config()
    reply = request_fn(cfg["base_url"] + "/v1/chat/completions", payload, cfg["api_key"])

    try:
        content = reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProxyError("chat completion missing content") from exc
    return parse_model_json(content)


def health(model: str = "Qwen3.8-Flash-Next-oQ4e-mtp") -> dict[str, Any]:
    """Report whether the local model endpoint answers and the model is loaded."""
    try:
        cfg = load_omlx_config()
        req = Request(cfg["base_url"] + "/v1/models",
                      headers={"Authorization": "Bearer " + cfg["api_key"]})
        with urlopen(req, timeout=10) as resp:
            ids = [m.get("id") for m in json.loads(resp.read()).get("data", [])]
        return {"ok": model in ids, "model": model,
                "loaded": ids, "base_url": cfg["base_url"]}
    except Exception as exc:  # any failure -> report, never crash
        return {"ok": False, "model": model, "error": str(exc)}
