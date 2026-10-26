"""P15.5.2: the art director flags an empty stretch and an off-brand (dark) page on the animatic, by scene."""
import json
import subprocess

from frameflow import artdirect, media


def test_empty_and_off_brand_scenes(tmp_path):
    out = tmp_path / "render"
    (out / "voice").mkdir(parents=True)
    (out / "plan.json").write_text(json.dumps({"scenes": [{"type": "kinetic", "lines": [{"say": "a"}]}, {"type": "flow", "lines": [{"say": "b"}]}]}))
    (out / "voice" / "durations.json").write_text(json.dumps({"total": 4.0, "lines": [{"id": "s0", "start": 0.0, "seconds": 1.8},
                                                                                     {"id": "s1", "start": 2.0, "seconds": 1.8}]}))
    subprocess.run([media.FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0xF3EEE4:s=270x480:d=2:r=12",
                    "-f", "lavfi", "-i", "color=c=0x14182A:s=270x480:d=2:r=12", "-filter_complex", "[0][1]concat=n=2:v=1",
                    str(out / "animatic.mp4")], check=True)
    r = artdirect.run(out)
    assert not r["pass"]
    assert any("scene 0" in p for p in r["checks"]["empty"]["problems"]), r["checks"]["empty"]
    assert r["checks"]["brand"]["problems"] and r["checks"]["brand"]["problems"][0].startswith("scene 1 (flow)")
    assert all("Change only that scene" in f["fix"] for f in artdirect.fixes(r))
