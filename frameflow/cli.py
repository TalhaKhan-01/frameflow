"""frameflow: command-line entry point. Each step also runs on its own (python -m frameflow.<module>).

    frameflow render <plan.json> [--out DIR] [--quality looks|delivery] [--mood MOOD]
    frameflow ideas collect|rank|list
    frameflow script <idea-id>
    frameflow qa <out-dir>
    frameflow validate <plan.json>
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(prog="frameflow", description="Automated Shorts for YouTube and Instagram.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="scene plan -> finished final.mp4")
    r.add_argument("plan")
    r.add_argument("--out")
    r.add_argument("--quality", default="looks", choices=["draft", "looks", "delivery"])
    r.add_argument("--mood")
    i = sub.add_parser("ideas", help="collect, rank and list ideas")
    i.add_argument("action", choices=["collect", "rank", "list"])
    i.add_argument("--hours", type=int, default=48)
    i.add_argument("--top", type=int, default=15)
    s = sub.add_parser("script", help="ranked idea -> scene plan (plans/<id>.json)")
    s.add_argument("idea_id", type=int)
    s.add_argument("--model", default="sonnet")
    q = sub.add_parser("qa", help="automatic quality gates on a render folder")
    q.add_argument("out_dir")
    v = sub.add_parser("validate", help="check a scene plan")
    v.add_argument("plan")
    a = ap.parse_args()
    if a.cmd == "render":
        from frameflow import pipeline
        print(json.dumps(pipeline.render(a.plan, a.out, a.quality, a.mood), indent=1))
    elif a.cmd == "ideas":
        from frameflow import ideas
        if a.action == "collect":
            print(json.dumps(ideas.collect(), indent=1))
        elif a.action == "rank":
            print(json.dumps(ideas.rank(a.hours), indent=1))
        else:
            for r in ideas.top(a.top):
                print(f"{r['score']:3} {r['lane']:15} {r['title'][:70]}\n    hook: {r['hook']}\n    India: {r['india_angle']}")
    elif a.cmd == "script":
        from frameflow import script
        print(json.dumps(script.write(a.idea_id, a.model), indent=1))
    elif a.cmd == "qa":
        from frameflow import qa
        sys.argv = ["qa", a.out_dir]
        qa.main()
    elif a.cmd == "validate":
        from frameflow import scene_plan
        errs = scene_plan.validate(json.loads(Path(a.plan).read_text()))
        print("\n".join(errs) or "valid")
        sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
