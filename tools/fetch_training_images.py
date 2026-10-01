"""Download verified free-license training illustrations from Wikimedia Commons.

Writes app/assets/training/<file> + manifest.json with attribution + license
per file (required by Commons CC licenses). Skips any file whose download
does not return a real image (Content-Type check) or whose license can't be
confirmed as free for commercial use. Fetched images must be verified visually
before shipping (some Commons "hallmark" files are unrelated objects).
"""
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "app" / "assets" / "training"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    "File:British hallmarks.jpg",
    "File:925CCM Silver.png",
    "File:Paul Storr Hallmark.jpg",
    "File:James Riviere - Desart Hallmarks.jpg",
    "File:Collier poinçon argent 925.JPG",
    "File:Lotový punc.png",
    "File:Poincon imprimerie royale.jpg",
    "File:Closeup view of the hallmarks in an antique silver spoon from Colonial era, photographed in West Bengal, India, December 7, 2023.jpg",
    "File:Beaker (Timbale) MET 118391.jpg",
    "File:M0354 2-226-63 2.jpg",
    "File:Falize Maker Mark.jpg",
    "File:Engelskkontroll.JPG",
    "File:Danskkontroll.JPG",
]

FREE_RE = re.compile(r"(cc|public domain|pd|mit|cc0)", re.I)


def api(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "EstateScout-dev/1.0 (proof build)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def main() -> None:
    data = api({
        "action": "query", "titles": "|".join(FILES),
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "1200",
        "format": "json",
    })
    pages = data["query"]["pages"]
    manifest = {}
    failed = []
    for key, page in pages.items():
        title = page.get("title", "")
        if not title or key.startswith("-"):
            print("SKIP (page not found):", key)
            failed.append(key)
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_clean = re.sub(r"<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", "")).strip()
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        # Prefer a sized thumb (Commons rate-limits bursty full-res fetches)
        url = info.get("thumburl") or info.get("url")
        if not url or not FREE_RE.search(license_clean):
            print("SKIP (license not confirmed free):", title, "->", license_clean or "?")
            failed.append(title)
            continue
        fname = title.replace("File:", "").replace("/", "-").replace(" ", "_")
        target = OUT_DIR / fname
        ok = False
        for attempt in range(3):
            if target.exists() and target.stat().st_size > 2000:
                ok = True
                break
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "EstateScout-dev/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    body = resp.read()
                if not ctype.startswith("image/"):
                    print("SKIP (not an image):", title, "->", ctype, len(body), "bytes")
                    break
                target.write_bytes(body)
                ok = True
                time.sleep(2)
            except urllib.error.HTTPError as e:
                print("  retry", attempt + 1, title, e.code)
                time.sleep(8 * (attempt + 1))
        if ok:
            manifest[fname] = {"source": info.get("url", url), "title": title,
                               "license": license_clean, "artist": artist[:120],
                               "bytes": target.stat().st_size}
            print("OK:", fname, "|", license_clean, "|", target.stat().st_size, "bytes")
        else:
            failed.append(title)
    if failed:
        print("FAILED:", failed)
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print("downloaded", len(manifest), "of", len(FILES))


if __name__ == "__main__":
    main()
