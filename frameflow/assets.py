"""Free stock media. CC0, public domain and CC BY only (no ShareAlike, no NonCommercial).

Images: Openverse, Wikimedia Commons, NASA Images (no key), Unsplash (free key UNSPLASH_ACCESS_KEY; skipped with an error row if unset).
Video:  NASA videos, Wikimedia Commons videos (no key), Internet Archive's Prelinger collection (archival, public domain).
        Archive licences elsewhere are set by uploaders and often wrong, so only Prelinger is searched.

    frameflow assets search "<query>" [--video]      list results from every source of that kind
    frameflow assets get "<query>" [--video]         download the first result of each source + ledger rows

Files go to data/assets/<source>/; every download adds a row to data/assets/ledger.json (source, licence, url, author),
which a render must carry into its own assets.json when it uses the file. Videos that aren't mp4 are converted to
H.264 mp4 without audio (the voice and music bed carry the sound). Unsplash downloads are reported to Unsplash, as its API rules ask.
"""
import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from frameflow import ideas, secrets

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "assets"
LEDGER = STORE / "ledger.json"
# CC0, public domain and CC BY only: ShareAlike (BY-SA) could force the whole video under the same licence.
COMMONS_OK = ("cc0", "cc by ", "cc-by-", "cc by-", "public domain", "pd")


def licence_ok(lic):
    low = lic.lower()
    # NonCommercial clashes with a monetised channel; NoDerivatives forbids the crops and overlays every scene makes
    return low.startswith(COMMONS_OK) and not {"sa", "nc", "nd"} & set(re.split(r"[\s-]+", low))


def quoted(url):
    """NASA asset links carry raw spaces; urllib refuses them."""
    return urllib.parse.quote(url.replace("http://", "https://", 1), safe=":/~?=&%")


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
        if not licence_ok(lic):
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


def unsplash(q, n=3):
    try:
        key = secrets.get("UNSPLASH_ACCESS_KEY")
    except SystemExit:
        raise RuntimeError("UNSPLASH_ACCESS_KEY not set (free key: unsplash.com/developers)")
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode({"query": q, "per_page": n, "client_id": key})
    out = []
    for r in get_json(url).get("results", [])[:n]:
        utm = "utm_source=frameflow&utm_medium=referral"   # Unsplash's attribution rule: link back with these
        out.append({"source": "Unsplash", "title": r.get("alt_description") or r.get("description") or q,
                    "file_url": r["urls"]["raw"] + "&w=2000&q=85&fm=jpg", "page": f"{r['links']['html']}?{utm}",
                    "licence": "Unsplash License (free commercial use; credit 'Photo by <author> on Unsplash')",
                    "author": r["user"]["name"], "id": r["id"],
                    "track": r["links"]["download_location"] + f"&client_id={key}"})
    return out


def nasa_video(q, n=3):
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "video"})
    out = []
    for item in get_json(url).get("collection", {}).get("items", []):
        d = item["data"][0]
        files = get_json(quoted(item["href"]))
        # ~medium is 720p-ish and a fraction of ~orig's size: plenty for a 1080x1920 crop
        mp4 = next((f for tag in ("~medium.mp4", "~mobile.mp4", "~orig.mp4") for f in files if f.endswith(tag)), None)
        if not mp4:
            continue
        out.append({"source": "NASA video", "title": d.get("title", q), "file_url": quoted(mp4),
                    "page": f"https://images.nasa.gov/details/{urllib.parse.quote(d['nasa_id'])}", "author": d.get("center") or "NASA",
                    "licence": "NASA media: generally not subject to copyright in the US; credit NASA (check for third-party marks)",
                    "id": d["nasa_id"], "video": True})
        if len(out) == n:
            break
    return out


def commons_video(q, n=3):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:video", "gsrnamespace": 6,
        "gsrlimit": n * 5, "prop": "imageinfo", "iiprop": "url|extmetadata"})
    out = []
    for page in sorted(get_json(url).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = re.sub(r"<[^>]+>", "", meta.get("LicenseShortName", {}).get("value", ""))
        if not licence_ok(lic):
            continue
        author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown")).strip()
        out.append({"source": "Commons video", "title": page["title"].removeprefix("File:"), "file_url": info["url"],
                    "page": info.get("descriptionurl"), "licence": lic, "author": author or "unknown", "id": str(page["pageid"]),
                    "video": True})
        if len(out) == n:
            break
    return out


def archive(q, n=3):
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        [("q", f"({q}) AND collection:prelinger AND mediatype:movies"), ("fl[]", "identifier"), ("fl[]", "title"),
         ("fl[]", "creator"), ("rows", n), ("output", "json")])
    out = []
    for doc in get_json(url).get("response", {}).get("docs", [])[:n]:
        ident = doc["identifier"]
        files = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}").get("files", [])
        mp4s = [f for f in files if f["name"].endswith(".mp4")]
        # 512Kb MPEG4 is the small derivative (a 6-minute film is ~25 MB instead of ~140 MB)
        pick = next((f for f in mp4s if f.get("format") == "512Kb MPEG4"), None) or next(iter(mp4s), None)
        if not pick:
            continue
        creator = doc.get("creator") or "Prelinger Archives"
        out.append({"source": "Internet Archive", "title": doc.get("title") or ident,
                    "file_url": f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(pick['name'])}",
                    "page": f"https://archive.org/details/{ident}", "author": creator if isinstance(creator, str) else ", ".join(creator),
                    "licence": "Public domain (Prelinger Archives); check the film for third-party marks",
                    "id": ident, "video": True})
    return out


SOURCES = {"openverse": openverse, "commons": commons, "nasa": nasa, "unsplash": unsplash}
VIDEO_SOURCES = {"nasa": nasa_video, "commons": commons_video, "archive": archive}


def search(q, per_source=3, video=False):
    results, errors = [], {}
    for name, fn in (VIDEO_SOURCES if video else SOURCES).items():
        try:
            results += fn(q, per_source)
        except Exception as e:
            errors[name] = str(e)
    return results, errors


def to_mp4(src):
    """webm/ogv from Commons → H.264 mp4, no audio, so every renderer and ffmpeg step takes it."""
    if not shutil.which("ffmpeg"):
        return src
    dest = src.with_suffix(".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an", "-c:v", "libx264", "-crf", "20",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)], check=True)
    src.unlink()
    return dest


def download(r):
    ext = (Path(urllib.parse.urlparse(r["file_url"]).path).suffix or (".mp4" if r.get("video") else ".jpg")).lower()[:5]
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", str(r["id"]))[:60]
    dest = STORE / r["source"].lower().replace(" ", "-") / f"{safe}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(ideas.fetch(r["file_url"], timeout=300 if r.get("video") else 60))
    if r.get("video") and dest.suffix != ".mp4":
        dest = to_mp4(dest)
    if r.get("track"):
        ideas.fetch(r["track"], timeout=30)   # Unsplash counts downloads through this call
    rows = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    row = {"file": str(dest.relative_to(ROOT)), "source": f"{r['source']}: {r['title']}", "licence": r["licence"],
           "url": r["page"], "author": r["author"]}
    rows = [x for x in rows if x["file"] != row["file"]] + [row]
    LEDGER.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return row


def get(q, video=False):
    results, errors = search(q, per_source=3, video=video)
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
