"""Stock images without API keys: Openverse, Wikimedia Commons, NASA Images. CC0, public domain and CC BY only (no ShareAlike, no NonCommercial).

    frameflow assets search "<query>" [--per-source 3]           list results from all three sources
    frameflow assets get "<query>"                              download the first result of each source + ledger rows

Files go to data/assets/<source>/; every download adds a row to data/assets/ledger.json (source, licence, url, author),
which a render must carry into its own assets.json when it uses the file.
"""
import json
import re
import urllib.parse
from pathlib import Path

from frameflow import ideas

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "assets"
LEDGER = STORE / "ledger.json"
# CC0, public domain and CC BY only: ShareAlike (BY-SA) could force the whole video under the same licence.
COMMONS_OK = ("cc0", "cc by ", "cc-by-", "cc by-", "public domain", "pd")


def get_json(url):
    for attempt in (1, 2):   # these free APIs are occasionally slow: one retry with a longer wait
        try:
            return json.loads(ideas.fetch(url, timeout=30 * attempt))
        except Exception:
            if attempt == 2:
                raise


def openverse(q, n=3):
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": q, "license": "cc0,pdm,by", "page_size": n, "mature": "false"})
    out = []
    for r in get_json(url).get("results", [])[:n]:
        out.append({"source": "Openverse", "title": r.get("title") or q, "file_url": r["url"], "page": r.get("foreign_landing_url") or r["url"],
                    "licence": f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip(), "author": r.get("creator") or "unknown",
                    "id": r["id"]})
    return out


def commons(q, n=3):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": n * 4, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600})
    out = []
    for page in sorted(get_json(url).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = re.sub(r"<[^>]+>", "", meta.get("LicenseShortName", {}).get("value", ""))
        low = lic.lower()
        if not low.startswith(COMMONS_OK) or "sa" in re.split(r"[\s-]+", low):
            continue
        author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown")).strip()
        out.append({"source": "Wikimedia Commons", "title": page["title"].removeprefix("File:"), "file_url": info.get("thumburl") or info["url"],
                    "page": info.get("descriptionurl"), "licence": lic, "author": author or "unknown", "id": str(page["pageid"])})
        if len(out) == n:
            break
    return out


def nasa(q, n=3):
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "image"})
    out = []
    for item in get_json(url).get("collection", {}).get("items", [])[:n]:
        d = item["data"][0]
        link = next((l["href"] for l in item.get("links", []) if l.get("rel") == "preview"), None)
        if not link:
            continue
        out.append({"source": "NASA", "title": d.get("title", q), "file_url": link,
                    "page": f"https://images.nasa.gov/details/{d['nasa_id']}", "author": d.get("center") or "NASA",
                    "licence": "NASA media: generally not subject to copyright in the US; credit NASA (check for third-party marks)",
                    "id": d["nasa_id"]})
    return out


SOURCES = {"openverse": openverse, "commons": commons, "nasa": nasa}


def search(q, per_source=3):
    results, errors = [], {}
    for name, fn in SOURCES.items():
        try:
            results += fn(q, per_source)
        except Exception as e:
            errors[name] = str(e)
    return results, errors


def download(r):
    ext = (Path(urllib.parse.urlparse(r["file_url"]).path).suffix or ".jpg").lower()[:5]
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", str(r["id"]))[:60]
    dest = STORE / r["source"].lower().replace(" ", "-") / f"{safe}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(ideas.fetch(r["file_url"], timeout=60))
    rows = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    row = {"file": str(dest.relative_to(ROOT)), "source": f"{r['source']}: {r['title']}", "licence": r["licence"],
           "url": r["page"], "author": r["author"]}
    rows = [x for x in rows if x["file"] != row["file"]] + [row]
    LEDGER.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return row


def get(q):
    results, errors = search(q, per_source=3)
    got, seen = [], set()
    for r in results:
        if r["source"] in seen:
            continue
        try:
            got.append(download(r))
            seen.add(r["source"])
        except Exception as e:
            errors[r["source"]] = str(e)
    return {"downloaded": got, "errors": errors}
