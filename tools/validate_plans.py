#!/usr/bin/env python3
"""Beat-sync validator for cut plans (stdlib only).

For every plans/<slug>.json that has a plans/<slug>_beats.json sibling it checks:
  * total_frames == sum(durationInFrames) and cut_count == len(video_adds)
  * boundaries_s (if present) match the cumulative clip durations
  * every internal cut lands on a beat (beat time minus the audio start
    offset) within TOLERANCE_FRAMES frames -- i.e. the cuts are really beat-synced
Exit status is non-zero on any problem, so it can gate CI.

Usage: python3 tools/validate_plans.py [plans_dir]
"""
import glob
import json
import os
import sys

FPS = 30.0
TOLERANCE_FRAMES = 2


def check_plan(plan, beats, fps=FPS, tol_frames=TOLERANCE_FRAMES):
    """Return a list of human-readable problems (empty = good)."""
    errs = []
    adds = plan.get("video_adds", [])
    durs = [int(a.get("durationInFrames", 0)) for a in adds]
    if any(d <= 0 for d in durs):
        errs.append("clip with non-positive durationInFrames")
    if plan.get("total_frames") is not None and plan["total_frames"] != sum(durs):
        errs.append("total_frames %s != sum of clip frames %s" % (plan["total_frames"], sum(durs)))
    if plan.get("cut_count") is not None and plan["cut_count"] != len(adds):
        errs.append("cut_count %s != %d video_adds" % (plan["cut_count"], len(adds)))
    cuts, acc = [], 0
    for d in durs[:-1]:
        acc += d
        cuts.append(acc / fps)
    bounds = plan.get("boundaries_s")
    if bounds:
        inner = bounds[1:1 + len(cuts)]
        for i, (b, c) in enumerate(zip(inner, cuts)):
            if abs(b - c) > 1.5 / fps:
                errs.append("boundary %d (%.3fs) disagrees with clip durations (%.3fs)" % (i + 1, b, c))
    offset = float((plan.get("audio_add") or {}).get("sourceStartFromInSeconds", plan.get("phase", 0.0)) or 0.0)
    beat_times = [b - offset for b in beats.get("beats", [])]
    if not beat_times:
        errs.append("beat map has no beats")
        return errs
    tol = tol_frames / fps
    for i, c in enumerate(cuts):
        nearest = min(abs(c - b) for b in beat_times)
        if nearest > tol:
            errs.append("cut %d at %.3fs is %.0f ms off the nearest beat" % (i + 1, c, nearest * 1000))
    return errs


def main(argv):
    pdir = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans")
    bad = 0
    for path in sorted(glob.glob(os.path.join(pdir, "*.json"))):
        if path.endswith("_beats.json"):
            continue
        bpath = path[:-5] + "_beats.json"
        if not os.path.exists(bpath):
            print("SKIP %s (no beat map)" % os.path.basename(path))
            continue
        with open(path) as f:
            plan = json.load(f)
        with open(bpath) as f:
            beats = json.load(f)
        errs = check_plan(plan, beats)
        print("%s %s" % ("FAIL" if errs else "ok  ", os.path.basename(path)))
        for e in errs:
            print("      - " + e)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
