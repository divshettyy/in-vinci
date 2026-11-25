#!/usr/bin/env python3
"""Render a cut plan locally with ffmpeg (stdlib only) — no ChatCut render needed.

Emits an ffmpeg command (as a shell script on stdout, or --run to execute) that
trims every `video_adds` entry from its source clip, applies the plan's 9:16
scale/crop, concatenates them at the plan fps and muxes the track window audio.
Source files are looked up in clips/ via the asset-id prefix table in
download_clips.sh (plans store the first 10 hex chars of each asset UUID).

Usage: python3 tools/export_ffmpeg.py plans/zora.json [--out out/zora.mp4] [--run]
"""
import json
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
_ROW = re.compile(r"\[([\w.\-]+)\]=([0-9a-f]{8})-([0-9a-f]{4})")


def asset_map(script_path=None):
    """{10-hex asset id prefix: filename} parsed from download_clips.sh."""
    script_path = script_path or os.path.join(ROOT, "download_clips.sh")
    with open(script_path, encoding="utf-8") as f:
        return {a + b[:2]: name for name, a, b in _ROW.findall(f.read())}


def video_filter(add, idx, fps):
    """Filter-graph chain for one clip -> label [v<idx>]."""
    dur = add["durationInFrames"] / float(fps)
    ss = float(add.get("sourceStartFromInSeconds", 0))
    f = "[%d:v]trim=start=%.3f:duration=%.3f,setpts=PTS-STARTPTS," % (idx, ss, dur)
    if add.get("width") and add.get("height"):
        # Plan scales the clip to width x height and offsets it by left/top
        # inside the canvas; equivalent to scale then crop at (-left, -top).
        x, y = max(0, -int(add.get("left", 0))), max(0, -int(add.get("top", 0)))
        f += "scale=%d:%d,crop=%d:%d:%d:%d," % (add["width"], add["height"], W, H, x, y)
    else:
        f += "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d," % (W, H, W, H)
    return f + "fps=%g,setsar=1[v%d]" % (fps, idx)


def build_command(plan, clips_dir, out, fps=None, assets=None):
    """Return the ffmpeg argv list for `plan`. Raises KeyError on unknown assets."""
    adds = plan["video_adds"]
    fps = fps or round(plan["total_frames"] / plan["length_s"])
    assets = assets or asset_map()
    files, filters = [], []
    for i, a in enumerate(adds):
        name = assets[a["assetId"]]
        files.append(os.path.join(clips_dir, name))
        filters.append(video_filter(a, i, fps))
    n = len(adds)
    filters.append("".join("[v%d]" % i for i in range(n)) + "concat=n=%d:v=1:a=0[v]" % n)
    cmd = ["ffmpeg", "-y"]
    for f in files:
        cmd += ["-i", f]
    audio = plan.get("audio_add") or {}
    cmd += ["-ss", "%.3f" % float(audio.get("sourceStartFromInSeconds", 0)),
            "-i", os.path.join(ROOT, plan.get("window") or "windows/%s_19s.mp3" % plan["slug"])]
    af = []
    fade = float(audio.get("audioFadeOut", 0))
    length = plan["total_frames"] / float(fps)
    if fade > 0:
        af = ["-af", "afade=t=out:st=%.3f:d=%.3f" % (max(0.0, length - fade), fade)]
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "%d:a" % n]
    cmd += af + ["-t", "%.3f" % length, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    return cmd


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    plan_path = args[0]
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    out = "out/%s.mp4" % plan.get("slug", "reel")
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    try:
        cmd = build_command(plan, os.path.join(ROOT, "clips"), out)
    except KeyError as e:
        print("unknown asset id %s (not in download_clips.sh)" % e, file=sys.stderr)
        return 1
    if "--run" in argv:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        return subprocess.call(cmd)
    print("#!/usr/bin/env bash\nmkdir -p %s\n%s" % (shlex.quote(os.path.dirname(out) or "."),
                                                    " ".join(shlex.quote(c) for c in cmd)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
