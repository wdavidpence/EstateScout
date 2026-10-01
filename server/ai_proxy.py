"""EstateScout AI proxy — Codex backend (user's ChatGPT/Codex subscription).

Proof-phase backend chosen by the user (2026-10-01): use Codex auth for
gpt-5.6-luna now; switch to an official API key at store publication.

Design contract (do not break):
  - The model NEVER draws and NEVER supplies executable behavior. It only
    returns {observations, verdict, confidence} with relative coordinates;
    the app draws red circles with fixed local code from model-supplied
    coords. Coordinates are validated/clamped server-side to [0,1] and
    capped at MAX_CIRCLES before the client sees them.
  - Codex OAuth tokens are read from ~/.codex/auth.json at runtime and
    refreshed when expired; they are never logged, returned to the client,
    or committed.

Proxy API (served by server.py):
  POST /api/analyze  {image: dataURL, note?: string}  ->  AnalysisResult
  GET  /api/health   ->  {ok, model, error?}
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CODEX_AUTH = Path.home() / ".codex" / "auth.json"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_BASE = "https://chatgpt.com/backend-api/codex"
CODEX_MODEL = "gpt-5.6-luna"
CODEX_ACCOUNT_ID = "20050f57-2157-4167-86dd-290da830c817"
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


def load_codex_config(path: Path = CODEX_AUTH) -> dict[str, str]:
    """Return {access_token, refresh_token, model, base_url} from Codex auth."""
    data = json.loads(path.read_text(encoding="utf-8"))
    tokens = data.get("tokens") or {}
    if not tokens.get("access_token") or not tokens.get("refresh_token"):
        raise ProxyError("no codex tokens in auth.json")
    return {"access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "model": CODEX_MODEL, "base_url": CODEX_BASE}


def refresh_codex_tokens(refresh_token: str) -> dict[str, str]:
    """Exchange the refresh token; returns fresh {access_token, refresh_token}."""
    body = json.dumps({"grant_type": "refresh_token",
                       "client_id": CODEX_CLIENT_ID,
                       "refresh_token": refresh_token}).encode()
    req = urllib.request.Request(
        CODEX_TOKEN_URL, data=body,
        headers={"Content-Type": "application/json",
                 "Originator": "HermesAgent"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec: fixed endpoint
        data = json.loads(resp.read())
    if "access_token" not in data:
        raise ProxyError("token refresh failed: %s" % data.get("error"))
    return {"access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token)}


def codex_request(url: str, body: dict[str, Any], access_token: str,
                  account_id: str = CODEX_ACCOUNT_ID) -> str:
    """POST to the Codex responses endpoint (stream SSE) and return the
    concatenated assistant text. The backend requires store=false and
    stream=true."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream",
                 "chatgpt-account-id": account_id,
                 "Originator": "HermesAgent"})
    chunks: list[str] = []
    with urllib.request.urlopen(req, timeout=300) as resp:  # nosec
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:])
            except json.JSONDecodeError:
                continue
            if event.get("type") == "response.output_text.delta":
                chunks.append(event.get("delta", ""))
            elif event.get("type") == "response.error":
                raise ProxyError("codex error: %s"
                                 % json.dumps(event.get("error"))[:200])
    if not chunks:
        raise ProxyError("no assistant text in codex response stream")
    return "".join(chunks)


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


def build_payload(data_url: str, note: str = "") -> dict[str, Any]:
    """Build the Codex responses payload for one image + optional note."""
    match = re.match(r"data:(image/[a-z+]+);base64,([A-Za-z0-9+/=]+)$",
                    data_url)
    if not match:
        raise ProxyError("image must be a base64 data URL")
    media_type, b64 = match.group(1), match.group(2)
    if len(b64) > 8 * 1024 * 1024:
        raise ProxyError("image too large (max ~6 MB)")
    user_text = ("Owner note: " + note) if note else \
        "Identify marks and material in this photo."
    return {
        "model": CODEX_MODEL,
        "store": False,
        "stream": True,
        "instructions": SYSTEM_PROMPT,
        "input": [{
            "type": "message", "role": "user",
            "content": [
                {"type": "input_image",
                 "image_url": "data:%s;base64,%s" % (media_type, b64)},
                {"type": "input_text", "text": user_text},
            ],
        }],
    }


def analyze_image(data_url: str, note: str = "",
                  request_fn=codex_request) -> dict[str, Any]:
    """Send one image (+optional note) via the Codex backend; return
    the sanitized analysis. Refreshes the OAuth token once on 401."""
    payload = build_payload(data_url, note)  # validates data URL first
    cfg = load_codex_config()
    url = cfg["base_url"] + "/responses"
    try:
        content = request_fn(url, payload, cfg["access_token"])
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):  # expired token: refresh once and retry
            fresh = refresh_codex_tokens(cfg["refresh_token"])
            content = request_fn(url, payload, fresh["access_token"])
        else:
            raise ProxyError("model unreachable: HTTP %s" % err.code) from err
    return parse_model_json(content)


def health(model: str = CODEX_MODEL) -> dict[str, Any]:
    """Report whether the Codex backend answers and the model id is listed."""
    try:
        cfg = load_codex_config()
        req = urllib.request.Request(
            cfg["base_url"] + "/models?client_version=0.154.0",
            headers={"Authorization": "Bearer " + cfg["access_token"],
                     "chatgpt-account-id": CODEX_ACCOUNT_ID,
                     "Originator": "HermesAgent"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            ids = [m.get("slug")
                   for m in json.loads(resp.read()).get("models", [])]
        return {"ok": model in ids, "model": model, "loaded": ids,
                "base_url": cfg["base_url"]}
    except Exception as exc:  # any failure -> report, never crash
        return {"ok": False, "model": model, "error": str(exc)}
