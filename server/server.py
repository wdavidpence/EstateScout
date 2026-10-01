"""Local dev server for the EstateScout proof phase.

Serves the static app from ../app and exposes the AI + data proxy under /api:
  POST /api/analyze       -> server/ai_proxy.analyze_image
  GET  /api/health        -> server/ai_proxy.health
  GET  /api/silver-price  -> price_service.get_prices()
  *    /api/items[/<id>]  -> collection.py over data/items.json (dev store)
  *    /api/library[/<id>] -> same store under data/library.json

Proof-phase only: binds 127.0.0.1, no TLS, no billing. Before any store
submission this exact API surface must move to a hosted backend with real
auth, rate limits and the Luna API key (see plan).

Run:  python3 server/server.py  (then open http://127.0.0.1:4178/)
"""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import ai_proxy  # noqa: E402
import price_service  # noqa: E402
import collection  # noqa: E402

APP_DIR = ROOT / "app"
MODEL = "mtplx-flash-next-bare-speed"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        target = (APP_DIR / rel).resolve()
        if not str(target).startswith(str(APP_DIR.resolve())) or not target.is_file():
            return self._json(404, {"error": "not found"})
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_api(self, method: str) -> None:  # path like /api/analyze
        path = urlparse(self.path).path
        sub = path[len("/api"):]
        if method == "GET" and sub == "/health":
            return self._json(200, ai_proxy.health(MODEL))
        if method == "POST" and sub == "/analyze":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 9 * 1024 * 1024:
                    return self._json(413, {"error": "request too large"})
                body = json.loads(self.rfile.read(length))
                image = body.get("image", "")
                note = str(body.get("note", ""))[:500]
                if not image:
                    return self._json(400, {"error": "image required"})
                return self._json(200, ai_proxy.analyze_image(image, note, MODEL))
            except ai_proxy.ProxyError as exc:
                return self._json(422, {"error": str(exc)})
            except (OSError, ValueError) as exc:
                return self._json(502, {"error": "model unreachable: %s" % exc})
        if method == "GET" and sub == "/silver-price":
            return self._json(200, price_service.get_prices())
        m = re.match(r"^/(items|library)(?:/([\w.-]+))?$", sub)
        if m:
            store = collection if m.group(1) == "items" else None
            item_id = m.group(2)
            if store is None:  # library has no py module; dev store is empty
                return self._json(200, {"items": [], "total": 0})
            if method == "GET":
                if item_id:
                    item = store.get_item(item_id)
                    return self._json(200, item or {"error": "not found"})
                return self._json(200, store.get_collection())
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except (OSError, ValueError):
                return self._json(400, {"error": "bad body"})
            if method == "POST":
                new_id = store.add_item_note(body.get("item", {}))
                return self._json(200, {"id": new_id})
            if method == "PUT" and item_id:
                current = store.load_notes()
                current["items"] = [body.get("item", {}) if it.get("id") == item_id else it
                                    for it in current["items"]]
                store.save_notes(current)
                return self._json(200, {"id": item_id})
            if method == "DELETE" and item_id:
                return self._json(200, {"deleted": store.delete_item(item_id)})
        return self._json(404, {"error": "unknown api path"})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self._handle_api("GET")
        return self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path.startswith("/api/"):
            return self._handle_api("POST")
        return self._json(404, {"error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if urlparse(self.path).path.startswith("/api/"):
            return self._handle_api("PUT")
        return self._json(404, {"error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        if urlparse(self.path).path.startswith("/api/"):
            return self._handle_api("DELETE")
        return self._json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # quiet, single-line
        print("HTTP", format % args, flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 4178), Handler)
    print("EstateScout dev server on http://127.0.0.1:4178/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
