"""Step-by-step progress of a pipeline job, for Frameflow Control's Making panel.

    with progress.step("render frames", scenes=12) as info:
        ...
        info["seconds_of_video"] = 97.1      # added to the 'end' event

Each step writes a 'start' line, then 'end' (with seconds and info) or 'fail' (with the error, SystemExit included),
to logs/progress-<day>.jsonl. Steps nest: the line carries its parent step's id. daily.main sets the file
(FF_PROGRESS) for make / revise / reflow / post; without it every call is a no-op. Writing progress never raises:
a full disk or a bad value must not cost a video.
"""
import datetime as dt
import itertools
import json
import os
import time
from contextlib import contextmanager

_stack = []
_ids = itertools.count(1)


def _write(event):
    path = os.environ.get("FF_PROGRESS")
    if not path:
        return
    try:
        event = {"t": dt.datetime.now().isoformat(timespec="seconds"), "pid": os.getpid(), **event}
        with open(path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


@contextmanager
def step(name, **detail):
    sid = f"{os.getpid()}-{next(_ids)}"
    parent = _stack[-1] if _stack else None
    _write({"ev": "start", "id": sid, "parent": parent, "step": name, "detail": detail})
    _stack.append(sid)
    info, began = {}, time.time()
    try:
        yield info
    except BaseException as e:   # SystemExit and Ctrl-C too: the panel must see where a job ended
        _write({"ev": "fail", "id": sid, "step": name, "seconds": round(time.time() - began, 1), "info": info,
                "error": f"{type(e).__name__}: {e}"[:500]})
        raise
    else:
        _write({"ev": "end", "id": sid, "step": name, "seconds": round(time.time() - began, 1), "info": info})
    finally:
        _stack.pop()


def note(text, **detail):
    """A single line under the current step (a decision, a count, a retry)."""
    _write({"ev": "note", "parent": _stack[-1] if _stack else None, "text": text, "detail": detail})
