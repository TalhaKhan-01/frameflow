"""The Pilot (agent-browser) in Frameflow's dedicated Chrome (PM2 frameflow-chrome, DevTools 127.0.0.1:7307):
YouTube Studio uploads until the API audit passes, and Facebook/Instagram whenever the Meta API fails (dead token).

    python -m frameflow.pilot youtube <video_id>        upload + publish; prints {"url": ...}
    python -m frameflow.pilot instagram <video_id>      post the Reel; prints {"url": ...}
    python -m frameflow.pilot facebook <video_id>       post the Reel as the Page; prints {"url": ...}
    python -m frameflow.pilot photos <img>... [--fb-caption F] [--ig-caption F]   card slides via Business Suite
    python -m frameflow.pilot check                     is the Chrome up and signed in to both?

Only for videos Talha approved (publish.upload enforces it). The steps mirror what worked by hand on 2026-10-25/26:
Studio's text boxes take execCommand('insertText'); Instagram's caption editor only takes real key input.
Every final click is a real click and counts only when the site confirms it, and a link is reported only when the
live post shows our caption (2026-10-26: unchecked clicks left a draft and reported yesterday's Reel as posted).
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
DRY = bool(__import__("os").environ.get("FRAMEFLOW_PILOT_DRY"))   # stop before the final Post/Share/Publish (testing)


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
    # 2026-10-26 a JS click on Publish didn't land and the Short stayed a draft: click for real, and again until the
    # 'Video published' dialog shows; nothing else counts as published
    published = "/Video published/.test(document.querySelector('ytcp-video-share-dialog')?.innerText||'')"
    for _ in range(4):
        if js(published):
            break
        try:
            ab("click", "#done-button")
        except PilotError:
            js("document.querySelector('#done-button')?.click(); 1")
        try:
            wait_for(published, 45, what="the published dialog")
            break
        except PilotError:
            pass
    else:
        raise PilotError("Studio never showed 'Video published': the Short is probably still a draft")
    link = js("(() => { const a=[...document.querySelectorAll('ytcp-video-share-dialog a, a')].find(x=>/youtube\\.com\\/shorts\\/|youtu\\.be\\//.test(x.href)); return a ? a.href : ''; })()") or link
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
    ig_drop([out / "final.mp4"])
    js("(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='OK'); b&&b.click(); return 1; })()")
    time.sleep(1.5)
    js("(() => { const s=[...document.querySelectorAll('svg[aria-label]')].find(x=>/select crop/i.test(x.getAttribute('aria-label'))); if(!s) return 0; (s.closest('button,[role=button]')||s).dispatchEvent(new MouseEvent('click',{bubbles:true})); return 1; })()")
    time.sleep(1)
    js("(() => { const e=[...document.querySelectorAll('span,div')].find(e=>e.children.length===0 && e.textContent.trim()==='9:16'); e&&(e.closest('button,[role=button]')||e).click(); return !!e; })()")
    nxt = "(() => { const n=[...document.querySelectorAll('div[role=button],button')].find(e=>e.textContent.trim()==='Next'); n&&n.click(); return !!n; })()"
    js(nxt)
    time.sleep(3)
    # no custom cover: its input takes files only by DOM.setFileInputFiles, which kills the tab (see ig_drop)
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
    if DRY:
        return {"dry": True, "at": "Share button"}
    ig_share()
    return {"url": ig_find(first, "reel"), "mode": "pilot"}


def ig_drop(files):
    """Drop files on the New post dialog. ab upload (DOM.setFileInputFiles) got the tab killed by Chrome 154
    ('bad IPC message') on 2026-10-26, and Instagram ignores a change event on its input; a drop works."""
    wait_for("[...document.querySelectorAll('div[role=dialog] *')].some(x=>x.children.length===0 && /Drag photos and videos here/.test(x.textContent))",
             30, what="the New post dialog")
    js("(() => { const e=[...document.querySelectorAll('div[role=dialog] *')].find(x=>x.children.length===0 && /Drag photos and videos here/.test(x.textContent)); "
       "let z=e; for(let k=0;k<4;k++) z=z.parentElement; z.setAttribute('data-ffdrop','1'); return 1; })()")
    inject("instagram.com", "drop:[data-ffdrop]", files)
    wait_for("/Crop|Something went wrong/.test(document.querySelector('div[role=dialog]')?.innerText||'')", 120, what="Instagram to take the file")
    if js("/Something went wrong/.test(document.body.innerText)"):
        raise PilotError("Instagram: 'Something went wrong' after the upload")


def inject(url_part, selector, files):
    env = {"PATH": f"{NODE_BIN}:/usr/bin:/bin", "HOME": str(Path.home())}
    r = subprocess.run(["node", str(ROOT / "scripts" / "inject-file.mjs"), str(PORT), url_part, selector, *map(str, files)],
                       capture_output=True, text=True, timeout=600, env=env)
    if r.returncode:
        raise PilotError(f"inject: {(r.stderr or r.stdout)[-300:]}")


def ig_share():
    """A real click on Share, then Instagram's own 'has been shared' line; 'Sharing' merely vanishing proved nothing."""
    ab("click", ref(r'button "Share"'))
    wait_for("/has been shared|went wrong|couldn.t be shared/i.test(document.querySelector('div[role=dialog]')?.innerText||'')",
             900, 10, "Instagram to confirm the share")
    if not js("/has been shared/i.test(document.querySelector('div[role=dialog]')?.innerText||'')"):
        raise PilotError("Instagram didn't share the post: " + str(js("(document.querySelector('div[role=dialog]')?.innerText||'').slice(0,120)")))


def ig_find(first, kind):
    """Link of the newest post whose live caption starts like ours: never the newest post blindly
    (on 2026-10-26 that reported yesterday's Reel as today's)."""
    ab("open", f"https://www.instagram.com/{IG_HANDLE}/", timeout=60)
    time.sleep(6)
    links = js("[...new Set([...document.querySelectorAll('a')].map(x=>x.href).filter(h=>/\\/(reel|p)\\//.test(h)))].slice(0,4)")
    for link in links if isinstance(links, list) else []:
        ab("open", link, timeout=60)
        time.sleep(5)
        if first[:30] in str(js("document.body.innerText")):
            code = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)", link).group(1)
            return f"https://www.instagram.com/{'reel' if kind == 'reel' else 'p'}/{code}/"
    raise PilotError("Instagram said shared, but no recent post carries today's caption")


# ---------- Facebook (web, as the Thirdspace Page) ----------
# Used when the Graph API token is dead. The caption goes in as one paste event: Facebook's editor drops Enter key
# presses but keeps the line breaks of a paste. 

FB_BOX = "div[contenteditable=true][role=textbox]"


def fb_caption(text, box=FB_BOX):
    wait_for(f"!!document.querySelector({json.dumps(box)})", 60, what="Facebook's caption box")
    js(f"(() => {{ const e=document.querySelector({json.dumps(box)}); e.focus(); const dt=new DataTransfer(); "
       f"dt.setData('text/plain', {json.dumps(text)}); "
       "e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true})); return 1; })()")
    time.sleep(1)
    typed = str(js(f"document.querySelector({json.dumps(box)}).innerText"))
    first = text.split("\n")[0].strip()
    if first[:40] not in typed:
        raise PilotError("the caption didn't take in Facebook's editor")


def fb_click(label):
    return js("(() => { const b=[...document.querySelectorAll('div[role=dialog] div[role=button], div[role=button], button')]"
              f".find(e=>(e.getAttribute('aria-label')||e.textContent.trim())==={json.dumps(label)} && e.getAttribute('aria-disabled')!=='true'); "
              "b&&b.click(); return !!b; })()")


def facebook(video_id):
    out, p = pack_of(video_id)
    caption = p.get("fb_caption", p["ig_caption"])
    connect()
    ab("open", "https://www.facebook.com/reels/create", timeout=90)
    wait_for("document.querySelectorAll('input[type=file]').length > 0", 60, what="the Reel composer")
    ab("upload", "input[type=file]", out / "final.mp4", timeout=600)
    wait_for("/Describe your reel/.test(document.body.innerHTML)", 180, what="the video to load")
    fb_caption(caption)
    if not fb_click("Next"):
        raise PilotError("no Next button in the Reel composer")
    wait_for("[...document.querySelectorAll('div[role=button]')].some(e=>e.textContent.trim()==='Post')", 60, what="the settings step")
    js("(() => { const s=[...document.querySelectorAll('[role=switch]')].find(x=>/AI label/.test(x.closest('[role=button]')?.textContent||'')); "
       "if(s && s.getAttribute('aria-checked')!=='true') s.click(); return !!s; })()")
    time.sleep(1)
    if DRY:
        return {"dry": True, "at": "Post button"}
    wait_for("(() => { const b=[...document.querySelectorAll('div[role=button]')].find(e=>e.textContent.trim()==='Post'); return b && b.getAttribute('aria-disabled')!=='true'; })()",
             600, 5, "Facebook to finish uploading")
    ab("click", ref(r'button "Post"'))   # a real click: a JS .click() on this div didn't always post
    wait_for("!location.pathname.startsWith('/reels/create')", 120, 3, "Facebook to accept the Reel")
    url = fb_published(caption)
    return {"url": url, "mode": "pilot"}


def fb_published(caption, minutes=10):
    """The new Reel's link, from the 'Your reel has been published' notification (its content_id holds the post id).
    Only returned once the live Reel shows this caption, so an older Reel can never be reported as today's."""
    import base64
    first = caption.split("\n")[0].strip()[:40]
    end = time.time() + minutes * 60
    while time.time() < end:
        ab("open", "https://www.facebook.com/notifications", timeout=60)
        time.sleep(6)
        ids = js("[...document.querySelectorAll('a')].filter(a=>/Your reel has been published/.test(a.innerText)).map(a=>new URL(a.href).searchParams.get('content_id')).filter(Boolean)")
        for cid in ids if isinstance(ids, list) else []:
            post = base64.b64decode(cid + "==").decode(errors="ignore").split(":")[-1]
            ab("open", f"https://www.facebook.com/{FB_PAGE}/posts/{post}", timeout=60)
            time.sleep(8)
            href, text = js("location.href"), str(js("document.body.innerText"))
            if first in text and "/reel/" in str(href):
                return str(href).split("?")[0]
        time.sleep(30)
    raise PilotError("Facebook took the Reel, but no published Reel with today's caption showed up")


FB_PAGE = "122094160959534001"
BS_ASSET = "1475788295611893"   # the Thirdspace Page in Meta Business Suite


# ---------- Habit card photos: Meta Business Suite, one composer for both ----------
# Instagram's web editor answers any photo post with 'Something went wrong' and facebook.com rejects photos set by
# The Pilot; Business Suite's composer takes them (posted fine on 2026-10-26). It has no AI label, so Reels don't use it.

def photos(images, captions):
    """captions: {"facebook": text, "instagram": text}, only the platforms to post to. Returns {platform: url}."""
    connect()
    ab("open", f"https://business.facebook.com/latest/composer/?asset_id={BS_ASSET}", timeout=90)
    wait_for("[...document.querySelectorAll('[role=button],button')].some(e=>e.textContent.trim()==='Add photo/video')", 60, what="the composer")
    names = {"facebook": "Thirdspace", "instagram": IG_HANDLE}
    combo = ref(r'combobox "Post to')
    ab("click", combo)
    time.sleep(1.5)
    for platform, name in names.items():   # options are toggles: make each match what we want
        line = next((l for l in ab("snapshot", "-i").splitlines() if re.search(rf'option "{name}"', l)), "")
        if line and ("[selected" in line) != (platform in captions):
            ab("click", "@" + re.search(r"ref=(e\d+)", line).group(1))
            time.sleep(1)
    ab("press", "Escape")
    want = " and ".join(names[p] for p in names if p in captions)
    if want not in ab("snapshot", "-i"):
        raise PilotError(f"couldn't set 'Post to' to {want}")
    # the page makes its file input on click and opens the system picker: keep the input in the page instead
    js("(() => { const orig=HTMLInputElement.prototype.click; HTMLInputElement.prototype.click=function(){ if(this.type==='file'){ "
       "this.setAttribute('data-ffup','1'); if(!this.isConnected){ this.style.display='none'; document.body.appendChild(this);} return; } return orig.call(this); }; return 1; })()")
    js("(() => { const b=[...document.querySelectorAll('[role=button],button')].find(e=>e.textContent.trim()==='Add photo/video'); b&&b.click(); return !!b; })()")
    wait_for("!!document.querySelector('[data-ffup]')", 20, what="the photo input")
    inject("business.facebook.com", "[data-ffup]", images)
    wait_for(f"(document.body.innerText.match(/\\d+ x \\d+/g)||[]).length >= {len(images)}", 120, what="all slides to load")
    if len(captions) > 1:
        ab("click", ref(r'switch "Customise post for Facebook and Instagram"'))
        time.sleep(2)
    for platform, text in captions.items():
        if len(captions) > 1:
            ab("click", ref(rf'tab "{platform.capitalize()}"'))
            time.sleep(1.5)
        bs_caption(text)
    if DRY:
        return {"dry": True, "at": "Publish button"}
    ab("click", ref(r'button "Publish"'))
    wait_for("/Your post is published|went wrong|couldn.t/i.test(document.body.innerText)", 600, 5, "Business Suite to publish")
    if not js("/Your post is published/.test(document.body.innerText)"):
        raise PilotError("Business Suite didn't publish the post")
    links = {}
    if "instagram" in captions:
        links["instagram"] = ig_find(captions["instagram"].split("\n")[0].strip(), "post")
    if "facebook" in captions:
        links["facebook"] = bs_fb_link(captions["facebook"].split("\n")[0].strip()[:40])
    return links


def bs_caption(text):
    """Paste into the visible caption box (one per platform once customised) and check it took whole."""
    vis = "[...document.querySelectorAll('[contenteditable=true]')].find(e=>e.offsetParent!==null)"
    js(f"(() => {{ const e={vis}; e.focus(); const dt=new DataTransfer(); dt.setData('text/plain', {json.dumps(text.strip())}); "
       "e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true})); return 1; })()")
    time.sleep(1.5)
    norm = lambda s: "\n".join(l.strip() for l in str(s).strip().splitlines() if l.strip())
    if norm(js(f"{vis}.innerText")) != norm(text):
        raise PilotError("the caption didn't take whole in Business Suite's editor")


def bs_fb_link(first):
    """The Facebook post's link, from its row in Business Suite's published posts (matched on the caption)."""
    ab("open", f"https://business.facebook.com/latest/posts/published_posts?asset_id={BS_ASSET}", timeout=90)
    for _ in range(10):
        time.sleep(8)
        found = js(f"(()=>{{ const row=[...document.querySelectorAll('[role=row], tr')].find(r=>r.innerText.includes({json.dumps(first)})); if(!row) return 0; "
                   f"const c=[...row.querySelectorAll('span,div')].find(e=>e.children.length===0&&e.textContent.includes({json.dumps(first[:20])})); c&&c.click(); return 1; }})()")
        if found:
            time.sleep(6)
            m = re.search(r"set=pcb\.(\d+)", str(js("[...document.querySelectorAll('a')].map(a=>a.href).join(' ')")))
            if m:
                return f"https://www.facebook.com/{FB_PAGE}/posts/{m.group(1)}"
        ab("open", f"https://business.facebook.com/latest/posts/published_posts?asset_id={BS_ASSET}", timeout=90)
    raise PilotError("published, but the Facebook post's link wasn't found in Business Suite")


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
    ap.add_argument("what", choices=["youtube", "instagram", "facebook", "photos", "check"])
    ap.add_argument("video_id", nargs="?")
    ap.add_argument("images", nargs="*")
    ap.add_argument("--fb-caption", help="photos: Facebook caption file (posts to Facebook)")
    ap.add_argument("--ig-caption", help="photos: Instagram caption file (posts to Instagram)")
    a = ap.parse_args()
    import fcntl   # one Pilot run at a time: the Short and the card post go out at the same minute and share one tab
    (ROOT / "logs").mkdir(exist_ok=True)
    lock = open(ROOT / "logs" / "pilot.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        if a.what == "photos":   # every positional argument is an image here
            caps = {k: Path(f).read_text() for k, f in (("facebook", a.fb_caption), ("instagram", a.ig_caption)) if f}
            r = photos([a.video_id, *a.images], caps)
        else:
            r = check() if a.what == "check" else {"youtube": youtube, "instagram": instagram, "facebook": facebook}[a.what](a.video_id)
    finally:
        ab("close", check=False)   # detaches; the dedicated Chrome keeps running under PM2
    print(json.dumps(r))


if __name__ == "__main__":
    main()
