#!/usr/bin/env bash
# Frames of the latest posted Short for the scroll-scrubbed product sequence (72 WebP frames, 360 px wide).
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=public/media/latest/preview.mp4
rm -f public/frames/f*.webp
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")
FPS=$(python3 -c "print(72/$DUR)")
ffmpeg -v error -i "$SRC" -vf "fps=$FPS,scale=360:-2" -c:v libwebp -quality 70 -frames:v 72 public/frames/f%02d.webp
ls public/frames | wc -l
