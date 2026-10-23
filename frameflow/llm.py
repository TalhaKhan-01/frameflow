"""Model calls through Claude Code (`claude -p`), inside Talha's Pro plan: no API key, no API bill.

Each call is lean: no tools unless asked, no project settings, a short system prompt, structured JSON output.
Every call's token usage is appended to data/llm-usage.jsonl so the cost per video can be measured.
"""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE_LOG = ROOT / "data" / "llm-usage.jsonl"
CONFIG_DIR = os.environ.get("FRAMEFLOW_CLAUDE_CONFIG", str(Path.home() / ".claude-personal"))


class LLMError(RuntimeError):
    pass


def call(prompt, system, schema=None, model="haiku", tools="", add_dirs=(), purpose="", timeout=600, effort=None):
    """Run one headless call; return structured_output (when a schema is given) or the text result."""
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--no-session-persistence",
           "--setting-sources", "", "--strict-mcp-config", "--system-prompt", system, "--tools", tools]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    if effort:
        cmd += ["--effort", effort]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    env = dict(os.environ, CLAUDE_CONFIG_DIR=CONFIG_DIR)
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd="/tmp")
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise LLMError(f"claude -p returned no JSON: {(r.stdout or r.stderr)[-600:]}") from None
    u = d.get("usage", {})
    USAGE_LOG.parent.mkdir(exist_ok=True)
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "purpose": purpose, "model": model,
                            "input": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
                            "cache_create": u.get("cache_creation_input_tokens", 0), "output": u.get("output_tokens", 0),
                            "seconds": round(time.time() - t0, 1), "error": d.get("is_error")}) + "\n")
    if d.get("is_error"):
        raise LLMError(str(d.get("result"))[:600])
    if schema:
        if d.get("structured_output") is None:
            raise LLMError("no structured_output in reply")
        return d["structured_output"]
    return d.get("result", "")


def usage_summary(purpose_prefix=""):
    rows = [json.loads(l) for l in USAGE_LOG.read_text().splitlines()] if USAGE_LOG.exists() else []
    rows = [r for r in rows if r["purpose"].startswith(purpose_prefix)]
    total = sum(r["input"] + r["cache_read"] + r["cache_create"] + r["output"] for r in rows)
    return {"calls": len(rows), "tokens": total}
