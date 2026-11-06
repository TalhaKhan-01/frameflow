"""The coach: Frameflow's learning loop (P11, redesigned 5 Nov 2026 at Talha's request; replaces frameflow.lessons).

Every episode is an experiment. The coach keeps a playbook of short, general rules for the desks that write words
(the writer, the visual-cue picker). Each rule targets one review row (hook, clarity, flow, readability, ...) and carries
a Beta(alpha, beta) belief that it raises that row. It works like a multi-armed bandit (Thompson sampling):

  before a make   playbook(desk): the proven rules (champions) plus up to `trials` rules under test, chosen by drawing
                  from each trial rule's Beta belief, so promising rules are tried more and weak ones less.
  after a make    record(out): every review row is compared with its running baseline (an exponential mean over earlier
                  episodes). A rule under test gets credit (alpha) when its target row beat the baseline, blame (beta)
                  when it fell below, half of each on a tie. Champions are tracked the same way, so a rule that stops
                  working is demoted.
  promotion       P(rule helps) >= 0.85 after 3+ trials -> champion; <= 0.25 after 3+ trials, or 6 trials undecided -> retired.
  new rules       when fewer than `trials` + 1 rules are under test, one model call writes new candidates for the weakest
                  rows from the judges' fixes of the latest episodes. Talha's own notes (revise, reject, /feedback)
                  become candidates with a head start (alpha 2), because the owner's word weighs most.
  slow signal     stats(video_id, ...): 48 h later, a video that beat the channel median retention (else views) gives its
                  rules half a point of credit, one below it half a point of blame. The fast signal (the review) steers;
                  the audience re-weights.
  practice        practice(episode_dir): between makes (and while the daily run is paused) the coach re-writes a past
                  episode's script with and without one trial rule and table-reads both (text only, no render), a cheap
                  extra trial for writer rules.
  tickets         rows the text desks can't move (look, framing, captions, habit: the template's job) become engineering
                  tickets in research/coach-tickets.jsonl for the next Claude session, never prompt rules.

    python -m frameflow.coach status
    python -m frameflow.coach record <episode-dir>
    python -m frameflow.coach practice <episode-dir> [--rule ID]
    python -m frameflow.coach note "<Talha's words>" [--source TEXT]

State: research/coach.json (rules, baselines, history). Tickets: research/coach-tickets.jsonl.
"""
import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

from frameflow import llm

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "research" / "coach.json"
TICKETS = ROOT / "research" / "coach-tickets.jsonl"

# Which desk can move which review row (rows are "script <row>" from the table read, "screen <row>" from the screening).
DESKS = {
    "writer": ["script hook", "script clarity", "script wit", "script flow", "script accuracy", "script variety",
               "script ending", "screen story"],
    "visuals": ["screen readability", "screen package", "screen story", "screen seen_heard"],
}
TEMPLATE_ROWS = ["screen look", "screen framing", "screen captions", "screen habit"]
EMA = 0.4                # weight of the newest episode in a row's baseline
TIE = 0.25               # a row within this of its baseline is a tie
TRIALS = 2               # rules under test per desk per episode
MAX_CHAMPIONS = 10       # per desk; the weakest is demoted when a new one is promoted
PROMOTE, RETIRE, MIN_TRIALS, MAX_TRIALS = 0.85, 0.25, 3, 6


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"rules": [], "baselines": {}, "history": [], "next_id": 1}


def save(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1))


def p_helps(r, draws=4000, rng=random):
    """P(theta > 0.5) under Beta(alpha, beta), by sampling (stdlib only)."""
    return sum(rng.betavariate(r["alpha"], r["beta"]) > 0.5 for _ in range(draws)) / draws


def add_rule(s, desk, row, text, source, alpha=1.0):
    r = {"id": f"R{s['next_id']}", "desk": desk, "row": row, "text": text.strip(), "source": source, "status": "trial",
         "alpha": alpha, "beta": 1.0, "trials": 0, "created": now(), "updated": now(), "log": []}
    s["next_id"] += 1
    s["rules"].append(r)
    return r


# ---------- before a make ----------
def playbook(desk, out=None, rng=random):
    """The rules text for one desk's prompt: champions, then this episode's trial rules (Thompson sampling).
    Writes <out>/coach-used.json (appending this desk) so record() knows which rules were in the episode."""
    s = load()
    champs = [r for r in s["rules"] if r["desk"] == desk and r["status"] == "champion"]
    trials = sorted((r for r in s["rules"] if r["desk"] == desk and r["status"] == "trial"),
                    key=lambda r: -rng.betavariate(r["alpha"], r["beta"]))[:TRIALS]
    if out:
        f = Path(out) / "coach-used.json"
        used = json.loads(f.read_text()) if f.exists() else {}
        used[desk] = {"champions": [r["id"] for r in champs], "trials": [r["id"] for r in trials]}
        f.write_text(json.dumps(used, indent=1))
    if not champs and not trials:
        return ""
    lines = [f"- {r['text']}" for r in champs + trials]
    return "House rules learned from earlier episodes (follow them where they fit):\n" + "\n".join(lines)


# ---------- after a make ----------
def rows_of(out):
    rev = json.loads((Path(out) / "review.json").read_text())
    return rev["rows"], rev.get("fixes", [])


def credit(r, delta, why):
    """delta: +1 helped, -1 hurt, 0 tie; weight scales it (the slow signal uses 0.5)."""
    return update(r, 1.0 if delta > 0 else (0.0 if delta < 0 else 0.5), why)


def update(r, share, why, weight=1.0):
    r["alpha"] += weight * share
    r["beta"] += weight * (1 - share)
    r["trials"] += 1 if weight >= 1 else 0
    r["updated"] = now()
    r["log"].append(f"{now()[:10]} {why}")
    r["log"] = r["log"][-12:]
    return r


def decide(s):
    """Promote, demote and retire on the current beliefs. Returns a list of changes for the report."""
    changes = []
    for r in s["rules"]:
        p = p_helps(r)
        if r["status"] == "trial" and r["trials"] >= MIN_TRIALS and p >= PROMOTE:
            r["status"] = "champion"
            changes.append(f"{r['id']} promoted (P helps {p:.2f}): {r['text']}")
        elif r["status"] == "trial" and r["trials"] >= MIN_TRIALS and (p <= RETIRE or r["trials"] >= MAX_TRIALS):
            r["status"] = "retired"
            changes.append(f"{r['id']} retired (P helps {p:.2f}): {r['text']}")
        elif r["status"] == "champion" and r["trials"] >= MIN_TRIALS + 3 and p < 0.5:
            r["status"] = "trial"
            changes.append(f"{r['id']} back under test (P helps {p:.2f})")
    for desk in DESKS:
        champs = sorted((r for r in s["rules"] if r["desk"] == desk and r["status"] == "champion"),
                        key=lambda r: r["alpha"] / (r["alpha"] + r["beta"]))
        for r in champs[:max(0, len(champs) - MAX_CHAMPIONS)]:
            r["status"] = "retired"
            changes.append(f"{r['id']} retired to keep {MAX_CHAMPIONS} champions")
    return changes


def record(out, propose=True):
    """Score the episode's rules against each row's baseline, update the baselines, decide, and top up candidates."""
    out = Path(out)
    s = load()
    if any(h["episode"] == out.name for h in s["history"]):
        return {"skipped": f"{out.name} already recorded"}
    rows, fixes = rows_of(out)
    used = json.loads((out / "coach-used.json").read_text()) if (out / "coach-used.json").exists() else {}
    base = s["baselines"]
    deltas = {k: (v - base[k]) if k in base else 0.0 for k, v in rows.items()}
    by_id = {r["id"]: r for r in s["rules"]}
    scored = []
    for desk, u in used.items():
        for rid in u.get("champions", []) + u.get("trials", []):
            r = by_id.get(rid)
            if not r or r["row"] not in rows or r["row"] not in base:
                continue
            d = deltas[r["row"]]
            credit(r, 0 if abs(d) < TIE else d, f"{out.name}: {r['row']} {rows[r['row']]} vs baseline {base[r['row']]:.2f}")
            scored.append(rid)
    for k, v in rows.items():
        base[k] = round(v if k not in base else (1 - EMA) * base[k] + EMA * v, 3)
    changes = decide(s)
    tickets = [{"at": now(), "episode": out.name, "row": f"screen {f['row']}", "fix": f["fix"]}
               for f in fixes if f"screen {f.get('row')}" in TEMPLATE_ROWS]
    if tickets:
        with TICKETS.open("a") as fh:
            fh.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in tickets)
    total = sum(rows.values())
    s["history"].append({"episode": out.name, "at": now(), "total": total, "rows": rows, "scored": scored, "changes": changes})
    save(s)
    new = propose_rules(out) if propose else []
    return {"episode": out.name, "total": total, "scored": scored, "changes": changes, "new": [r["id"] for r in new],
            "tickets": len(tickets)}


PROPOSE_SYSTEM = """You coach the desks of a daily 85-second news show (The Daily Habit: 8 stories, read by the narrator Habit,
for Indians aged 18-30). From the judges' fixes on recent episodes, write NEW general rules that will raise the weakest
review rows in FUTURE episodes. A rule is one sentence, general (it applies to any episode, not "fix segment 3"),
concrete and checkable ("Name who said a number in the same sentence as the number"), and fits the fixed format
(open starts with "Breaking:", 8 segments of 22-28 spoken words, numbers spoken as words, outro "Make learning a Habit.").
Desks: writer = the script's words; visuals = which picture, logo or article page each story shows. Give each rule the
one row it should raise (from the list you're given). Don't repeat a rule already in the playbook or one already retired."""

PROPOSE_SCHEMA = {"type": "object", "required": ["rules"], "properties": {"rules": {"type": "array", "maxItems": 4, "items": {
    "type": "object", "required": ["desk", "row", "text"], "properties": {
        "desk": {"type": "string", "enum": list(DESKS)}, "row": {"type": "string"}, "text": {"type": "string"}}}}}}


def weakest(s, n=4):
    rows = [k for k in s["baselines"] if any(k in v for v in DESKS.values())]
    return sorted(rows, key=lambda k: s["baselines"][k])[:n]


def propose_rules(out=None, owner=None, source=None):
    """Top up rules under test from the latest fixes, or turn the owner's words into candidates (alpha 2)."""
    s = load()
    trial = [r for r in s["rules"] if r["status"] == "trial"]
    if owner is None and len(trial) >= (TRIALS + 1) * len(DESKS):
        return []
    eps = sorted(p for p in (ROOT / "out" / "show").glob("*daily-habit-ep*") if (p / "review.json").exists())[-3:]
    if out and Path(out) not in eps:
        eps.append(Path(out))
    fixes = [f"[{e.name}] {f.get('row')}: {f['fix']}" for e in eps for f in rows_of(e)[1]]
    known = "\n".join(f"{r['id']} [{r['desk']}/{r['row']}] ({r['status']}) {r['text']}" for r in s["rules"]) or "none"
    rows = {d: v for d, v in DESKS.items()}
    ask = (f"Rows each desk can move: {json.dumps(rows)}\nWeakest rows now (baseline 0-2): "
           + ", ".join(f"{k} {s['baselines'][k]:.2f}" for k in weakest(s)) + f"\n\nPlaybook so far:\n{known}\n\n"
           + (f"THE OWNER (Talha) SAID, weigh this most:\n{owner}\n\n" if owner else "")
           + "Recent judges' fixes:\n" + "\n".join(fixes[-30:]) + "\n\nWrite up to 4 new rules.")
    got = llm.call(ask, PROPOSE_SYSTEM, PROPOSE_SCHEMA, model="sonnet", purpose="coach.propose", effort="medium", timeout=600)
    new = []
    for g in got["rules"]:
        row = g["row"] if g["row"] in DESKS[g["desk"]] else next((r for r in DESKS[g["desk"]] if r.endswith(" " + g["row"])), None)
        if row:
            new.append(add_rule(s, g["desk"], row, g["text"], source or ("owner" if owner else f"fixes up to {eps[-1].name if eps else '-'}"),
                                alpha=2.0 if owner else 1.0))
    save(s)
    return new


# ---------- the slow signal ----------
def stats(video_id, out_dir, metric, value, channel):
    """48 h stats: `value` of `metric` (e.g. average % viewed) against the channel's earlier values. Half a point of credit
    or blame for every rule used in the video. Needs 3 earlier videos to compare."""
    import statistics
    f = Path(out_dir) / "coach-used.json"
    if value is None or len(channel) < 3 or not f.exists():
        return "Coach: not scored yet (needs 3 earlier videos and the rules used)."
    med = statistics.median(channel)
    s = load()
    ids = {i for u in json.loads(f.read_text()).values() for i in u.get("champions", []) + u.get("trials", [])}
    for r in s["rules"]:
        if r["id"] in ids:
            update(r, 1.0 if value > med else (0.0 if value < med else 0.5), f"{video_id}: {metric} {value} vs median {med}", weight=0.5)
    s["history"].append({"episode": video_id, "at": now(), "audience": {metric: value, "median": med}, "rules": sorted(ids)})
    changes = decide(s)
    save(s)
    return f"Coach: {metric} {value} vs channel median {med:.1f}: {len(ids)} rule(s) {'credited' if value > med else 'blamed'}." + \
           (" " + "; ".join(changes) if changes else "")


# ---------- practice between makes ----------
def practice(ep_dir, rule_id=None):
    """Re-write a past episode's script twice (playbook with and without one trial writer rule) and table-read both.
    Text only. The difference on the rule's row is one more (practice) trial for that rule."""
    from frameflow import show
    ep = Path(ep_dir)
    data = json.loads((ep / "research.json").read_text())
    s = load()
    pool = [r for r in s["rules"] if r["desk"] == "writer" and r["status"] == "trial" and r["row"].startswith("script ")]
    if rule_id:
        pool = [r for r in pool if r["id"] == rule_id]
    if not pool:
        return {"skipped": "no writer rule under test"}
    rule = min(pool, key=lambda r: r["trials"])
    champs = "\n".join(f"- {r['text']}" for r in s["rules"] if r["desk"] == "writer" and r["status"] == "champion")
    scores = {}
    for arm, extra in (("without", ""), ("with", f"- {rule['text']}")):
        rules = "\n".join(x for x in (champs, extra) if x)
        tmp = ROOT / "out" / "coach-practice" / f"{ep.name}-{rule['id']}-{arm}"
        tmp.mkdir(parents=True, exist_ok=True)
        script = show.write(data, tmp, 0, ep.name[:10], rules=rules)
        scores[arm] = script["table_read"]["rows"]
    row = rule["row"].split(" ", 1)[1]
    d = scores["with"][row] - scores["without"][row]
    s = load()
    r = next(x for x in s["rules"] if x["id"] == rule["id"])
    update(r, 1.0 if d > 0 else (0.0 if d < 0 else 0.5), f"practice on {ep.name}: {row} {scores['with'][row]} with vs {scores['without'][row]} without")
    changes = decide(s)
    save(s)
    return {"rule": rule["id"], "row": row, "with": scores["with"], "without": scores["without"], "changes": changes}


def note(words, source="Talha"):
    return propose_rules(owner=words, source=source)


def status():
    s = load()
    out = {"baselines": s["baselines"], "rules": [{k: r[k] for k in ("id", "desk", "row", "status", "trials", "text")}
                                                  | {"p_helps": round(p_helps(r), 2)} for r in s["rules"] if r["status"] != "retired"],
           "retired": sum(r["status"] == "retired" for r in s["rules"]), "episodes": len(s["history"]),
           "totals": [h.get("total") for h in s["history"] if "total" in h][-10:]}
    return out


def main():
    ap = argparse.ArgumentParser(description="the coach: Frameflow's learning loop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("record"); r.add_argument("out"); r.add_argument("--no-propose", action="store_true")
    p = sub.add_parser("practice"); p.add_argument("out"); p.add_argument("--rule")
    n = sub.add_parser("note"); n.add_argument("words"); n.add_argument("--source", default="Talha")
    a = ap.parse_args()
    if a.cmd == "status":
        res = status()
    elif a.cmd == "record":
        res = record(a.out, propose=not a.no_propose)
    elif a.cmd == "practice":
        res = practice(a.out, a.rule)
    else:
        res = [r["text"] for r in note(a.words, a.source)]
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
