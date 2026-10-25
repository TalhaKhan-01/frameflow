"""Telegram Bot API, the small part Frameflow uses (stdlib only). The token comes from secrets (TELEGRAM_BOT_TOKEN)
and is never printed; every call goes only to the chat in research/automation.json.

    send(text, buttons)          message with an inline keyboard: buttons = [[(label, callback_data), ...], ...]
    send_file(kind, path, ...)   video / photo / document upload (bots may send files up to 50 MB)
    updates(offset)              long polling; no webhook, so no public URL is needed
"""
import json
import mimetypes
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from frameflow import secrets

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "research" / "automation.json"


class TelegramError(RuntimeError):
    pass


def config():
    return json.loads(CONFIG.read_text())


def _url(method):
    return f"https://api.telegram.org/bot{secrets.get('TELEGRAM_BOT_TOKEN')}/{method}"


def _scrub(text):
    return re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***", text)


def api(method, timeout=60, **params):
    data = json.dumps({k: v for k, v in params.items() if v is not None}).encode()
    req = urllib.request.Request(_url(method), data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise TelegramError(f"{method}: {e.code} {_scrub(e.read().decode('utf-8', 'replace'))[:300]}") from None
    except urllib.error.URLError as e:
        raise TelegramError(f"{method}: {e.reason}") from None
    if not d.get("ok"):
        raise TelegramError(f"{method}: {_scrub(str(d))[:300]}")
    return d["result"]


def keyboard(buttons):
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row] for row in buttons]} if buttons else None


def chat_id():
    cid = config().get("chat_id")
    if not cid:
        raise TelegramError("no chat_id in research/automation.json yet: send /start to the bot")
    return cid


def send(text, buttons=None, chat=None):
    """Plain-text message (no Markdown parsing, so titles and URLs never break it). Returns the message id."""
    return api("sendMessage", chat_id=chat or chat_id(), text=text[:4096], reply_markup=keyboard(buttons),
               disable_web_page_preview=True)["message_id"]


def clear_buttons(message_id, note=None):
    """Remove a message's buttons once answered (and optionally say what was chosen)."""
    try:
        api("editMessageReplyMarkup", chat_id=chat_id(), message_id=message_id, reply_markup={"inline_keyboard": []})
    except TelegramError:
        pass
    if note:
        send(note)


def answer(callback_id, text=None):
    try:
        api("answerCallbackQuery", callback_query_id=callback_id, text=text)
    except TelegramError:
        pass


def send_file(kind, path, caption="", buttons=None, extra=None):
    """kind: video | photo | document. Multipart upload; returns the message id."""
    method = {"video": "sendVideo", "photo": "sendPhoto", "document": "sendDocument"}[kind]
    boundary = uuid.uuid4().hex
    fields = {"chat_id": str(chat_id()), "caption": caption[:1024]}
    if buttons:
        fields["reply_markup"] = json.dumps(keyboard(buttons))
    fields.update({k: str(v) for k, v in (extra or {}).items()})
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    p = Path(path)
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{kind}\"; filename=\"{p.name}\"\r\n"
             f"Content-Type: {ctype}\r\n\r\n").encode() + p.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(_url(method), data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise TelegramError(f"{method}: {e.code} {_scrub(e.read().decode('utf-8', 'replace'))[:300]}") from None
    if not d.get("ok"):
        raise TelegramError(f"{method}: {_scrub(str(d))[:300]}")
    return d["result"]["message_id"]


def updates(offset=None, wait=25):
    """Long poll: returns as soon as there is an update, or after `wait` seconds with none."""
    data = json.dumps({"offset": offset, "timeout": wait, "allowed_updates": ["message", "callback_query"]}).encode()
    req = urllib.request.Request(_url("getUpdates"), data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=wait + 15) as r:
            d = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError) as e:
        raise TelegramError(f"getUpdates: {_scrub(str(e))[:200]}") from None
    return d.get("result", [])


def send_album(paths, caption=""):
    """Up to 10 photos as one album (sendMediaGroup); the caption sits on the first photo. Returns the first message id."""
    boundary = uuid.uuid4().hex
    media = [{"type": "photo", "media": f"attach://p{i}", **({"caption": caption[:1024]} if i == 0 and caption else {})}
             for i, _ in enumerate(paths[:10])]
    body = bytearray()
    for k, v in {"chat_id": str(chat_id()), "media": json.dumps(media)}.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for i, p in enumerate(paths[:10]):
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"p{i}\"; filename=\"{Path(p).name}\"\r\n"
                 f"Content-Type: image/png\r\n\r\n").encode() + Path(p).read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(_url("sendMediaGroup"), data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise TelegramError(f"sendMediaGroup: {e.code} {_scrub(e.read().decode('utf-8', 'replace'))[:300]}") from None
    return d["result"][0]["message_id"]
