#!/usr/bin/env python3
"""Remove cumulative frame-rounding drift from cut plans (stdlib only).

Clip lengths were rounded to whole frames one clip at a time, so the error
accumulates: late cuts in a reel could sit up to ~3 frames (100 ms) off the
beat. This re-derives durations from the plan's own beat-aligned
`boundaries_s` by rounding each *cumulative* boundary to a frame once and
differencing, so every cut is within half a frame of its beat and the total
length is unchanged.

Usage: python3 tools/retime_plans.py [--check] [plans_dir]
  --check  report plans that would change, write nothing (exit 1 if any)
"""
import glob
import json
import os
import sys

FPS = 30.0


def retime(plan, fps=FPS):
    """Return new per-clip frame counts, or None if the plan can't be retimed."""
    bounds = plan.get("boundaries_s")
    adds = plan.get("video_adds") or []
    total = plan.get("total_frames") or sum(a["durationInFrames"] for a in adds)
    if not bounds or len(bounds) < len(adds):
        return None
    edges = [0] + [int(round(b * fps)) for b in bounds[1:len(adds)]] + [int(total)]
    durs = [edges[i + 1] - edges[i] for i in range(len(adds))]
    if any(d < 1 for d in durs):
        return None
    return durs


def main(argv):
    check = "--check" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    pdir = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans")
    changed = 0
    for path in sorted(glob.glob(os.path.join(pdir, "*.json"))):
        if path.endswith("_beats.json"):
            continue
        with open(path) as f:
            plan = json.load(f)
        durs = retime(plan)
        if durs is None:
            continue
        old = [a["durationInFrames"] for a in plan["video_adds"]]
        if durs == old:
            continue
        changed += 1
        print("%s %s: %d clip(s) retimed" % ("would retime" if check else "retimed",
              os.path.basename(path), sum(a != b for a, b in zip(old, durs))))
        if not check:
            for a, d in zip(plan["video_adds"], durs):
                a["durationInFrames"] = d
            with open(path, "w") as f:
                json.dump(plan, f, indent=1, ensure_ascii=False)
                f.write("\n")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
