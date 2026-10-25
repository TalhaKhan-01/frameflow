"""The Pilot (agent-browser) in Frameflow's dedicated Chrome (PM2 frameflow-chrome, DevTools 127.0.0.1:7307):
YouTube Studio uploads until the API audit passes, and Instagram Reels the API won't take (over ~40 s).

    python -m frameflow.pilot youtube <video_id>        upload + publish; prints {"url": ...}
    python -m frameflow.pilot instagram <video_id>      post the Reel; prints {"url": ...}
    python -m frameflow.pilot check                     is the Chrome up and signed in to both?

Only for videos Talha approved (publish.upload enforces it). The steps mirror what worked by hand on 2026-10-25:
Studio's text boxes take execCommand('insertText'); Instagram's caption editor only takes real key input.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 7307
SESSION = "frameflow-pilot"
NODE_BIN = Path.home() / ".nvm/versions/node/v24.21.0/bin"
CHANNEL = "UCrcF7Q5J4kEENdJuA8BPQxQ"
IG_HANDLE = "madebythirdspace"


class PilotError(RuntimeError):
    pass


def ab(*args, timeout=180, check=True):
    env = {"PATH": f"{NODE_BIN}:/usr/bin:/bin", "HOME": str(Path.home())}
    r = subprocess.run(["agent-browser", "--session", SESSION, *map(str, args)], capture_output=True, text=True, timeout=timeout, env=env)
    out = (r.stdout + r.stderr).strip()
    if check and (r.returncode or out.startswith("✗")):
        raise PilotError(f"agent-browser {args[0]}: {out[-400:]}")
    return out


def js(code, timeout=60):
    """Evaluate in the page; returns the value (JSON-decoded when possible)."""
    out = ab("eval", code, timeout=timeout).splitlines()[-1]
    try:
        return json.loads(out)
    except ValueError:
        return out


def connect():
    ab("connect", str(PORT), timeout=60)


def wait_for(code, seconds=60, every=2.0, what="page state"):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if js(code):
                return True
        except PilotError:
            pass
        time.sleep(every)
    raise PilotError(f"timed out waiting for {what}")


def ref(pattern):
    """Ref of the first interactive element whose snapshot line matches the regex."""
    for line in ab("snapshot", "-i").splitlines():
        if re.search(pattern, line):
            m = re.search(r"ref=(e\d+)", line)
            if m:
                return "@" + m.group(1)
    raise PilotError(f"no element matching {pattern!r}")


def click(pattern):
    ab("click", ref(pattern))


def pack_of(video_id):
    from frameflow import videos
    row = videos.require_approved(video_id)
    out = Path(row["out_dir"])
    return out, json.loads((out / "publish.json").read_text())


# ---------- YouTube Studio ----------

def youtube(video_id):
    out, p = pack_of(video_id)
    connect()
    ab("open", "https://studio.youtube.com", timeout=90)
    wait_for(f"location.href.includes('{CHANNEL}')", 60, what="Studio signed in to the Thirdspace channel")
    js("(() => { const b=[...document.querySelectorAll('ytcp-button,button,ytcp-icon-button')].find(x=>/upload videos/i.test(x.getAttribute('aria-label')||x.textContent)); if(b){b.click();return 1;} document.querySelector('#upload-icon,#create-icon')?.click(); return 0; })()")
    time.sleep(2)
    if not js("document.querySelectorAll('input[type=file]').length"):
        click(r'"Upload videos"')
        time.sleep(2)
    ab("upload", "input[type=file]", out / "final.mp4", timeout=600)
    wait_for("document.querySelectorAll('#textbox[contenteditable=true]').length >= 2", 120, what="the details form")
    time.sleep(2)
    js("(() => { const b=[...document.querySelectorAll('#textbox[contenteditable=true]')]; "
       f"b[0].focus(); document.execCommand('selectAll'); document.execCommand('insertText', false, {json.dumps(p['yt_title'][:100])}); "
       f"b[1].focus(); document.execCommand('selectAll'); document.execCommand('insertText', false, {json.dumps(p['yt_description'][:5000])}); return 1; }})()")
    js("document.querySelector('tp-yt-paper-radio-button[name=VIDEO_MADE_FOR_KIDS_NOT_MFK]')?.click(); 1")
    if (out / "cover.png").exists():
        try:
            ab("upload", "input[type=file][accept*=image]", out / "cover.png", timeout=120)
        except PilotError as e:
            print(f"thumbnail: {e}", file=sys.stderr)
    js("(() => { const b=[...document.querySelectorAll('ytcp-button,button')].find(x=>/^show more$/i.test(x.textContent.trim())); b&&b.click(); return 1; })()")
    time.sleep(2)
    for pattern in (r'radio "No, my video doesn.t include paid promotion"', r'radio "Yes, AI was used"'):
        try:
            click(pattern)
        except PilotError as e:
            print(f"setting: {e}", file=sys.stderr)
    for tag in p.get("yt_tags", []):
        ab("focus", "ytcp-chip-bar input", check=False)
        ab("keyboard", "type", tag)
        ab("press", "Enter")
        time.sleep(0.3)
    js("(() => { const c=document.querySelector('#category'); if(!c) return 0; c.querySelector('ytcp-dropdown-trigger,#trigger')?.click(); return 1; })()")
    time.sleep(1.5)
    js("(() => { const o=[...document.querySelectorAll('tp-yt-paper-item,[role=option]')].find(x=>x.textContent.trim()==='Science & Technology'); o&&o.click(); return !!o; })()")
    for _ in range(3):
        js("document.querySelector('#next-button').click(); 1")
        time.sleep(2.5)
    js("(() => { const r=[...document.querySelectorAll('tp-yt-paper-radio-button')].find(x=>x.getAttribute('name')==='PUBLIC'); r&&r.click(); return !!r; })()")
    link = js("(() => { const a=[...document.querySelectorAll('a')].find(x=>/youtube\\.com\\/shorts\\/|youtu\\.be\\//.test(x.href)); return a ? a.href : ''; })()")
    wait_for("!document.querySelector('#done-button')?.hasAttribute('disabled')", 600, 5, "Studio's Publish button")
    js("document.querySelector('#done-button').click(); 1")
    wait_for("/Video published|published/i.test(document.body.innerText)", 120, what="the published dialog")
    js("document.querySelector('ytcp-video-share-dialog #close-button')?.click(); 1")
    if not link:
        raise PilotError("published, but no video link was found in the dialog")
    return {"url": link.split("?")[0], "mode": "studio"}


# ---------- Instagram (web) ----------

def instagram(video_id):
    out, p = pack_of(video_id)
    connect()
    ab("open", "https://www.instagram.com/", timeout=90)
    time.sleep(5)
    click(r'link "New post')
    time.sleep(2)
    try:
        click(r'link "Post Post"')
        time.sleep(2)
    except PilotError:
        pass
    ab("upload", "input[type=file]", out / "final.mp4", timeout=600)
    time.sleep(6)
    js("(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='OK'); b&&b.click(); return 1; })()")
    time.sleep(1.5)
    js("(() => { const s=[...document.querySelectorAll('svg[aria-label]')].find(x=>/select crop/i.test(x.getAttribute('aria-label'))); if(!s) return 0; (s.closest('button,[role=button]')||s).dispatchEvent(new MouseEvent('click',{bubbles:true})); return 1; })()")
    time.sleep(1)
    js("(() => { const e=[...document.querySelectorAll('span,div')].find(e=>e.children.length===0 && e.textContent.trim()==='9:16'); e&&(e.closest('button,[role=button]')||e).click(); return !!e; })()")
    nxt = "(() => { const n=[...document.querySelectorAll('div[role=button],button')].find(e=>e.textContent.trim()==='Next'); n&&n.click(); return !!n; })()"
    js(nxt)
    time.sleep(3)
    if (out / "cover.png").exists():
        try:
            ab("upload", "input[type=file][accept=\"image/jpeg,image/png\"]", out / "cover.png", timeout=120)
            time.sleep(3)
        except PilotError as e:
            print(f"cover: {e}", file=sys.stderr)
    js(nxt)
    wait_for("!!document.querySelector('div[role=dialog] div[contenteditable=true]')", 60, what="the caption box")
    ab("focus", "div[role=dialog] div[contenteditable=true]")
    ab("press", "Control+a")
    ab("press", "Backspace")
    for i, line in enumerate(p["ig_caption"].split("\n")):
        if i:
            ab("press", "Enter")
        if line:
            ab("keyboard", "inserttext", line)
    typed = js("document.querySelector('div[role=dialog] div[contenteditable=true]').innerText")
    first = p["ig_caption"].split("\n")[0].strip()
    if first[:40] not in str(typed):
        raise PilotError("the caption didn't take in Instagram's editor")
    js("(() => { const lab=[...document.querySelectorAll('div[role=dialog] span')].find(s=>s.textContent.trim()==='Add AI label'); let row=lab; "
       "for(let i=0;i<6&&row;i++){ row=row.parentElement; const s=row&&row.querySelector('input[type=checkbox],[role=switch]'); "
       "if(s){ if(!(s.checked||s.getAttribute('aria-checked')==='true')) s.click(); return 1; } } return 0; })()")
    js("(() => { const n=[...document.querySelectorAll('div[role=dialog] div[role=button], div[role=dialog] button')].find(e=>e.textContent.trim()==='Share'); n&&n.click(); return !!n; })()")
    wait_for("!/Sharing/.test(document.querySelector('div[role=dialog]')?.innerText||'')", 600, 10, "Instagram to finish sharing")
    time.sleep(3)
    link = js("location.href")
    if "/p/" not in str(link) and "/reel/" not in str(link):
        ab("open", f"https://www.instagram.com/{IG_HANDLE}/reels/", timeout=60)
        time.sleep(5)
        link = js("(() => { const a=[...document.querySelectorAll('a')].map(x=>x.href).find(h=>/\\/(reel|p)\\//.test(h)); return a||''; })()")
    m = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)", str(link))
    if not m:
        raise PilotError("shared, but the Reel's link wasn't found")
    url = f"https://www.instagram.com/reel/{m.group(1)}/"
    ab("open", url, timeout=60)   # the caption must be on the posted Reel (it once got lost)
    time.sleep(5)
    if first[:30] not in str(js("document.body.innerText")):
        print("warning: caption not visible on the posted Reel", file=sys.stderr)
        return {"url": url, "mode": "pilot", "caption_missing": True}
    return {"url": url, "mode": "pilot"}


def carousel(caption_file, images):
    """A photo carousel (Habit cards, 1080x1350): upload all slides at once, keep 4:5, caption, share, return the link."""
    caption = Path(caption_file).read_text()
    connect()
    ab("open", "https://www.instagram.com/", timeout=90)
    time.sleep(5)
    click(r'link "New post')
    time.sleep(2)
    try:
        click(r'link "Post Post"')
        time.sleep(2)
    except PilotError:
        pass
    ab("upload", "input[type=file]", *images, timeout=600)
    time.sleep(6)
    js("(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='OK'); b&&b.click(); return 1; })()")
    js("(() => { const s=[...document.querySelectorAll('svg[aria-label]')].find(x=>/select crop/i.test(x.getAttribute('aria-label'))); if(!s) return 0; (s.closest('button,[role=button]')||s).dispatchEvent(new MouseEvent('click',{bubbles:true})); return 1; })()")
    time.sleep(1)
    js("(() => { const e=[...document.querySelectorAll('span,div')].find(e=>e.children.length===0 && e.textContent.trim()==='4:5'); e&&(e.closest('button,[role=button]')||e).click(); return !!e; })()")
    nxt = "(() => { const n=[...document.querySelectorAll('div[role=button],button')].find(e=>e.textContent.trim()==='Next'); n&&n.click(); return !!n; })()"
    js(nxt)
    time.sleep(3)
    js(nxt)   # past the filters step
    wait_for("!!document.querySelector('div[role=dialog] div[contenteditable=true]')", 60, what="the caption box")
    ab("focus", "div[role=dialog] div[contenteditable=true]")
    ab("press", "Control+a")
    ab("press", "Backspace")
    for i, line in enumerate(caption.split("\n")):
        if i:
            ab("press", "Enter")
        if line:
            ab("keyboard", "inserttext", line)
    first = caption.split("\n")[0].strip()
    if first[:40] not in str(js("document.querySelector('div[role=dialog] div[contenteditable=true]').innerText")):
        raise PilotError("the caption didn't take in Instagram's editor")
    js("(() => { const n=[...document.querySelectorAll('div[role=dialog] div[role=button], div[role=dialog] button')].find(e=>e.textContent.trim()==='Share'); n&&n.click(); return !!n; })()")
    wait_for("!/Sharing/.test(document.querySelector('div[role=dialog]')?.innerText||'')", 600, 10, "Instagram to finish sharing")
    time.sleep(3)
    ab("open", f"https://www.instagram.com/{IG_HANDLE}/", timeout=60)
    time.sleep(5)
    link = js("(() => { const a=[...document.querySelectorAll('a')].map(x=>x.href).find(h=>/\\/p\\//.test(h)); return a||''; })()")
    m = re.search(r"/p/([A-Za-z0-9_-]+)", str(link))
    if not m:
        raise PilotError("shared, but the post's link wasn't found")
    url = f"https://www.instagram.com/p/{m.group(1)}/"
    ab("open", url, timeout=60)
    time.sleep(5)
    if first[:30] not in str(js("document.body.innerText")):
        print("warning: caption not visible on the posted carousel", file=sys.stderr)
        return {"url": url, "mode": "pilot", "caption_missing": True}
    return {"url": url, "mode": "pilot"}


def check():
    connect()
    ab("open", "https://studio.youtube.com", timeout=90)
    time.sleep(5)
    yt = CHANNEL in str(js("location.href"))
    ab("open", "https://www.instagram.com/", timeout=90)
    time.sleep(5)
    insta = "New post" in ab("snapshot", "-i")
    return {"chrome": True, "youtube_signed_in": yt, "instagram_signed_in": insta}


def main():
    ap = argparse.ArgumentParser(description="The Pilot in Frameflow's dedicated Chrome")
    ap.add_argument("what", choices=["youtube", "instagram", "carousel", "check"])
    ap.add_argument("video_id", nargs="?")
    ap.add_argument("images", nargs="*")
    a = ap.parse_args()
    try:
        if a.what == "carousel":   # video_id holds the caption file here
            r = carousel(a.video_id, a.images)
        else:
            r = check() if a.what == "check" else (youtube if a.what == "youtube" else instagram)(a.video_id)
    finally:
        ab("close", check=False)   # detaches; the dedicated Chrome keeps running under PM2
    print(json.dumps(r))


if __name__ == "__main__":
    main()
