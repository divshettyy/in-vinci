#!/usr/bin/env python3
"""Record the beat-grid drop (stdlib only).

The drop detector reports an onset time that usually falls between grid beats
(116-348 ms off in some maps). A hard cut can only land on a beat, so this adds a
non-destructive `drop_time_beat` field to each plans/*_beats.json: the beat
nearest `drop_time`. The raw `drop_time` is never modified.

Usage: python3 tools/snap_drop.py [--check] [beats_dir]
  --check  write nothing; exit 1 if any beat map is missing/stale
"""
import glob
import json
import os
import sys


def snap(beats):
    """Return the beat time nearest drop_time, or None if either is missing."""
    drop = beats.get("drop_time")
    bts = beats.get("beats") or []
    if drop is None or not bts:
        return None
    return round(min(bts, key=lambda b: abs(b - float(drop))), 3)


def main(argv):
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    d = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans")
    stale = 0
    for path in sorted(glob.glob(os.path.join(d, "*_beats.json"))):
        with open(path, encoding="utf-8") as f:
            beats = json.load(f)
        want = snap(beats)
        if want is None or beats.get("drop_time_beat") == want:
            continue
        stale += 1
        print("%s: drop_time %.3f -> drop_time_beat %.3f" % (os.path.basename(path), beats["drop_time"], want))
        if not check:
            beats["drop_time_beat"] = want
            with open(path, "w", encoding="utf-8") as f:
                json.dump(beats, f, indent=2)
                f.write("\n")
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
