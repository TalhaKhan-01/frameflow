# Frameflow (personal project)

Project context lives in the vault: read `vault/Docs/Handoff.md` first.

## Live demo: "start Frameflow and make a video about <topic>"
When Talha asks in plain words to start Frameflow / make a video about a topic, do exactly this and nothing else:

```
cd ~/Talha_Khan/Code/frameflow && uv run python -m frameflow.demo start "<the topic in his words>"
```

It launches the pipeline in the background and returns at once. Reply with its two output lines only (the topic it
matched and the Control link). Don't wait for it, don't poll it, don't run any other step: the making is shown live in
Frameflow Control (http://127.0.0.1:7310, Making panel) and the finished video arrives on Telegram. Nothing is posted.
Prepared topics are in `out/demo/<topic>/` (today: ISRO's Aditya-L1 solar eruption).
