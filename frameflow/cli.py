"""frameflow: command-line entry point. Each step also runs on its own (python -m frameflow.<module>).

    frameflow render <plan.json> [--out DIR] [--quality looks|delivery] [--mood MOOD]
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
    v = sub.add_parser("validate", help="check a scene plan")
    v.add_argument("plan")
    a = ap.parse_args()
    if a.cmd == "render":
        from frameflow import pipeline
        print(json.dumps(pipeline.render(a.plan, a.out, a.quality, a.mood), indent=1))
    elif a.cmd == "validate":
        from frameflow import scene_plan
        errs = scene_plan.validate(json.loads(Path(a.plan).read_text()))
        print("\n".join(errs) or "valid")
        sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
