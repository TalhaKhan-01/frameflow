"""frameflow: command-line entry point. Each step also runs on its own (python -m frameflow.<module>).

    frameflow make <idea-id>                      the whole chain for one idea (v1)
    frameflow make2 <brief.json>                  Quality v2 chain: writer + director skills -> render -> qa -> review
    frameflow direct <brief.json>                 Quality v2 front half only: script, storyboard, plan.json
    frameflow status | approve <id> | reject <id> <why>
    frameflow publish <id> | upload <id> [--only youtube|instagram] | posted <id> <yt> <ig> | stats <id> ... | learn
    frameflow render <plan.json> [--out DIR] [--quality looks|delivery] [--mood MOOD]
    frameflow ideas collect|rank|list
    frameflow script <idea-id>
    frameflow qa <out-dir>
    frameflow review <out-dir>
    frameflow validate <plan.json>
    frameflow web export|pin                      Studio web app snapshot (PIN-locked) + betadoc live numbers
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
    r.add_argument("--theme", help="visual identity in scenes/_shared/themes/ (default: plan's theme, else theme.css)")
    i = sub.add_parser("ideas", help="collect, rank and list ideas")
    i.add_argument("action", choices=["collect", "rank", "list"])
    i.add_argument("--hours", type=int, default=48)
    i.add_argument("--top", type=int, default=15)
    rv = sub.add_parser("review", help="full screening of a finished video (shorts-screening)")
    rv.add_argument("out_dir")
    for name in ("make2", "direct"):
        m2 = sub.add_parser(name, help="brief -> the studio board -> video" if name == "make2" else "brief -> writer + director -> plan only")
        m2.add_argument("brief")
        m2.add_argument("--out")
        m2.add_argument("--lane", default="how-tech-works")
        m2.add_argument("--skip-writer", action="store_true", help="reuse <out>/writer/script.json")
        m2.add_argument("--skip-director", action="store_true", help="reuse <out>/director/storyboard.json")
    sub.add_parser("status", help="list videos")
    wb = sub.add_parser("web", help="Studio web app snapshot: export | refresh | pin | open | lock")
    wb.add_argument("action", choices=["export", "refresh", "pin", "open", "lock"])
    wb.add_argument("reason", nargs="*")
    pf = sub.add_parser("profile", help="pipeline profiles: list | show | use <name> | save <name>")
    pf.add_argument("args", nargs="*")
    ap_ = sub.add_parser("approve", help="Talha approves a video after watching it")
    ap_.add_argument("video_id")
    rj = sub.add_parser("reject", help="send a video back")
    rj.add_argument("video_id")
    rj.add_argument("why")
    pb = sub.add_parser("publish", help="publish pack for an approved video")
    pb.add_argument("video_id")
    up = sub.add_parser("upload", help="approved video -> YouTube and/or Instagram (social-upload skill)")
    up.add_argument("video_id")
    up.add_argument("--only", choices=["youtube", "instagram", "facebook"])
    up.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    po = sub.add_parser("posted", help="record the live links")
    po.add_argument("video_id")
    po.add_argument("youtube_url")
    po.add_argument("instagram_url")
    stt = sub.add_parser("stats", help="48 h stats (YouTube public counts fetched; private numbers typed in)")
    stt.add_argument("video_id")
    for k in ("avg-viewed", "swiped", "yt-shares", "yt-subs", "ig-plays", "ig-likes", "ig-comments", "ig-shares", "ig-saves", "ig-avg-watch", "ig-follows"):
        stt.add_argument("--" + k, type=float)
    sub.add_parser("learn", help="weekly learning report into the vault")
    asx = sub.add_parser("assets", help="free stock images (Openverse, Commons, NASA, Unsplash) or --video (NASA, Commons, Internet Archive)")
    asx.add_argument("action", choices=["search", "get"])
    asx.add_argument("query")
    asx.add_argument("--video", action="store_true", help="search video sources instead of images")
    q = sub.add_parser("qa", help="automatic quality gates on a render folder")
    q.add_argument("out_dir")
    v = sub.add_parser("validate", help="check a scene plan")
    v.add_argument("plan")
    a = ap.parse_args()
    if a.cmd == "render":
        from frameflow import pipeline
        print(json.dumps(pipeline.render(a.plan, a.out, a.quality, a.mood, a.theme), indent=1))
    elif a.cmd == "ideas":
        from frameflow import ideas
        if a.action == "collect":
            print(json.dumps(ideas.collect(), indent=1))
        elif a.action == "rank":
            print(json.dumps(ideas.rank(a.hours), indent=1))
        else:
            for r in ideas.top(a.top):
                print(f"{r['score']:3} {r['lane']:15} {r['title'][:70]}\n    hook: {r['hook']}\n    India: {r['india_angle']}")
    elif a.cmd == "review":
        from frameflow import review
        sys.argv = ["review", a.out_dir]
        review.main()
    elif a.cmd == "profile":
        from frameflow import profiles
        profiles.main(a.args)
    elif a.cmd == "make2":
        from frameflow import videos
        print(json.dumps(videos.make2(a.brief, a.lane, a.out, a.skip_writer, a.skip_director), indent=1))
    elif a.cmd == "direct":
        from frameflow import direct
        print(json.dumps(direct.direct(a.brief, a.out, a.lane, a.skip_writer, a.skip_director), indent=1))
    elif a.cmd == "web":
        from . import webexport
        webexport.main([a.action, *a.reason])
    elif a.cmd == "status":
        from frameflow import videos
        for v in videos.listing():
            print(f"{v['status']:18} {v['review_total'] or '-':>2}/{20 if (v['note'] or '').startswith('v2') else 12} qa:{'ok' if v['qa_pass'] else '--'}  {v['lane']:15} {v['id']}")
    elif a.cmd in ("approve", "reject"):
        from frameflow import videos
        videos.set_status(a.video_id, "approved" if a.cmd == "approve" else "rejected", getattr(a, "why", ""))
        print(f"{a.video_id}: {a.cmd}d")
    elif a.cmd == "publish":
        from frameflow import publish
        print(json.dumps(publish.publish(a.video_id), indent=1))
    elif a.cmd == "upload":
        from frameflow import publish
        print(json.dumps(publish.upload(a.video_id, (a.only,) if a.only else ("youtube", "instagram", "facebook"), a.privacy), indent=1))
    elif a.cmd == "posted":
        from frameflow import publish
        print(json.dumps(publish.posted(a.video_id, a.youtube_url, a.instagram_url), indent=1))
    elif a.cmd == "stats":
        from frameflow import publish
        manual = {k.replace("-", "_"): v for k, v in vars(a).items() if v is not None and k not in ("cmd", "video_id")}
        print(json.dumps(publish.stats(a.video_id, manual), indent=1))
    elif a.cmd == "learn":
        from frameflow import publish
        print(json.dumps(publish.learn(), indent=1))
    elif a.cmd == "assets":
        from frameflow import assets
        if a.action == "search":
            res, errs = assets.search(a.query, video=a.video)
            for r in res:
                print(f"{r['source']:18} {r['licence'][:28]:28} {r['author'][:24]:24} {r['title'][:50]}")
            print(f"errors: {errs or 'none'}")
        else:
            print(json.dumps(assets.get(a.query, video=a.video), ensure_ascii=False, indent=1))
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
