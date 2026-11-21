#!/usr/bin/env python3
"""Put a cut on the drop (stdlib only).

A phonk edit should hit a hard cut on the beat drop. For each plan this moves
the internal cut nearest the drop onto the beat nearest the drop, by trading
frames between the two clips either side of that cut -- so the total length and
every other cut are untouched, and the moved cut stays beat-synced.

A cut is only moved when it is within --max-shift frames of the target (default
20, ~0.67 s) and both neighbouring clips stay at least MIN_CLIP_FRAMES long;
otherwise the plan is left alone. boundaries_s is updated to match.

Usage: python3 tools/align_drop.py [--check] [--max-shift N] [plans_dir]
  --check  report plans that would change, write nothing (exit 1 if any)
"""
import glob
import json
import os
import sys

FPS = 30.0
MIN_CLIP_FRAMES = 4
MAX_SHIFT = 20


def _offset(plan):
    return float((plan.get("audio_add") or {}).get("sourceStartFromInSeconds",
                                                    plan.get("phase", 0.0)) or 0.0)


def align(plan, beats, fps=FPS, max_shift=MAX_SHIFT):
    """Return (new_durations, info) or None when nothing should change.

    info = {"cut": 1-based cut index, "from": frame, "to": frame}.
    """
    drop = beats.get("drop_time")
    adds = plan.get("video_adds") or []
    durs = [int(a.get("durationInFrames", 0)) for a in adds]
    if drop is None or len(durs) < 2:
        return None
    off = _offset(plan)
    beat_t = [b - off for b in beats.get("beats", []) if b - off > 0]
    if not beat_t:
        return None
    target_t = min(beat_t, key=lambda b: abs(b - (float(drop) - off)))
    target = int(round(target_t * fps))
    edges, acc = [], 0
    for d in durs[:-1]:
        acc += d
        edges.append(acc)
    i = min(range(len(edges)), key=lambda k: abs(edges[k] - target))
    if edges[i] == target or abs(edges[i] - target) > max_shift:
        return None
    new = list(durs)
    delta = target - edges[i]            # >0: cut moves later
    new[i] += delta
    new[i + 1] -= delta
    if new[i] < MIN_CLIP_FRAMES or new[i + 1] < MIN_CLIP_FRAMES:
        return None
    return new, {"cut": i + 1, "from": edges[i], "to": target}


def apply(plan, new_durs):
    for a, d in zip(plan["video_adds"], new_durs):
        a["durationInFrames"] = d
    if plan.get("boundaries_s"):
        acc = 0
        b = [0.0]
        for d in new_durs[:-1]:
            acc += d
            b.append(round(acc / FPS, 3))
        tail = plan["boundaries_s"][len(b):]
        plan["boundaries_s"] = b + tail
    return plan


def main(argv):
    check = "--check" in argv
    max_shift = MAX_SHIFT
    args = []
    it = iter(argv[1:])
    for a in it:
        if a == "--max-shift":
            max_shift = int(next(it))
        elif not a.startswith("--"):
            args.append(a)
    pdir = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans")
    changed = 0
    for path in sorted(glob.glob(os.path.join(pdir, "*.json"))):
        if path.endswith("_beats.json"):
            continue
        bpath = path[:-5] + "_beats.json"
        if not os.path.exists(bpath):
            continue
        with open(path) as f:
            plan = json.load(f)
        with open(bpath) as f:
            beats = json.load(f)
        res = align(plan, beats, max_shift=max_shift)
        if not res:
            continue
        new, info = res
        changed += 1
        print("%s cut %d: frame %d -> %d" % (os.path.basename(path), info["cut"], info["from"], info["to"]))
        if not check:
            apply(plan, new)
            with open(path, "w") as f:
                json.dump(plan, f, indent=1, ensure_ascii=False)
                f.write("\n")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
