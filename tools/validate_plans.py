#!/usr/bin/env python3
"""Beat-sync validator for cut plans (stdlib only).

For every plans/<slug>.json that has a plans/<slug>_beats.json sibling it checks:
  * total_frames == sum(durationInFrames) and cut_count == len(video_adds)
  * boundaries_s (if present) match the cumulative clip durations
  * every internal cut lands on a beat (beat time minus the audio start
    offset) within TOLERANCE_FRAMES frames -- i.e. the cuts are really beat-synced
Exit status is non-zero on any problem, so it can gate CI.

Usage: python3 tools/validate_plans.py [--report] [plans_dir]
  --report  also print mean/max cut-to-beat offset in ms and cut pacing per plan
"""
import glob
import json
import os
import sys

FPS = 30.0
TOLERANCE_FRAMES = 2
MIN_CLIP_FRAMES = 4   # shorter than ~130 ms reads as a flicker/glitch, not a cut


def check_plan(plan, beats, fps=FPS, tol_frames=TOLERANCE_FRAMES):
    """Return a list of human-readable problems (empty = good)."""
    errs = []
    adds = plan.get("video_adds", [])
    durs = [int(a.get("durationInFrames", 0)) for a in adds]
    if any(d <= 0 for d in durs):
        errs.append("clip with non-positive durationInFrames")
    short = [i + 1 for i, d in enumerate(durs) if 0 < d < MIN_CLIP_FRAMES]
    if short:
        errs.append("clip(s) %s shorter than %d frames (flicker)" % (short, MIN_CLIP_FRAMES))
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


def cut_offsets_ms(plan, beats, fps=FPS):
    """Signed offset (ms) of each internal cut from its nearest beat.

    Negative = the cut lands early, positive = late. Handy for judging how
    tight a plan is beyond the pass/fail tolerance used by check_plan().
    """
    durs = [int(a.get("durationInFrames", 0)) for a in plan.get("video_adds", [])]
    offset = float((plan.get("audio_add") or {}).get("sourceStartFromInSeconds", plan.get("phase", 0.0)) or 0.0)
    beat_times = [b - offset for b in beats.get("beats", [])]
    if not beat_times:
        return []
    out, acc = [], 0
    for d in durs[:-1]:
        acc += d
        c = acc / fps
        nearest = min(beat_times, key=lambda b: abs(b - c))
        out.append(round((c - nearest) * 1000.0, 1))
    return out


def summarize_offsets(offs):
    """(mean abs ms, max abs ms) for a list from cut_offsets_ms; (0, 0) if empty."""
    if not offs:
        return 0.0, 0.0
    a = [abs(x) for x in offs]
    return round(sum(a) / len(a), 1), max(a)


def pacing(plan, fps=FPS):
    """Cut-rhythm stats for a plan: mean/min/max clip length (s), whether cuts
    accelerate toward the end (second-half mean clip shorter than first half --
    the usual phonk build into the drop), and whether every clip is the same
    length (monotone pacing). Returns None for plans with < 2 clips."""
    durs = [int(a.get("durationInFrames", 0)) for a in plan.get("video_adds", [])]
    durs = [d for d in durs if d > 0]
    if len(durs) < 2:
        return None
    h = len(durs) // 2
    first, second = durs[:h], durs[len(durs) - h:]
    f_mean, s_mean = sum(first) / len(first), sum(second) / len(second)
    return {
        "clips": len(durs),
        "mean_s": round(sum(durs) / len(durs) / fps, 2),
        "min_s": round(min(durs) / fps, 2),
        "max_s": round(max(durs) / fps, 2),
        "accelerates": s_mean < f_mean,
        "monotone": len(set(durs)) == 1,
    }


def drop_alignment_ms(plan, beats, fps=FPS):
    """Signed offset (ms) from the beat map's drop_time to the nearest internal
    cut, in plan time. A phonk edit should hit a cut ON the drop; None when the
    beat map has no drop_time or the plan has no internal cuts."""
    drop = beats.get("drop_time")
    if drop is None:
        return None
    durs = [int(a.get("durationInFrames", 0)) for a in plan.get("video_adds", [])]
    offset = float((plan.get("audio_add") or {}).get("sourceStartFromInSeconds", plan.get("phase", 0.0)) or 0.0)
    cuts, acc = [], 0
    for d in durs[:-1]:
        acc += d
        cuts.append(acc / fps)
    if not cuts:
        return None
    target = float(drop) - offset
    nearest = min(cuts, key=lambda c: abs(c - target))
    return round((nearest - target) * 1000.0, 1)


def main(argv):
    report = "--report" in argv
    argv = [a for a in argv if a != "--report"]
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
        if report:
            mean_ms, max_ms = summarize_offsets(cut_offsets_ms(plan, beats))
            print("      cut offset from beat: mean %.1f ms, max %.1f ms" % (mean_ms, max_ms))
            da = drop_alignment_ms(plan, beats)
            if da is not None:
                print("      drop: nearest cut %+.1f ms from drop_time%s" % (
                    da, "" if abs(da) <= 1000 * TOLERANCE_FRAMES / FPS else "  (NO CUT ON THE DROP)"))
            pc = pacing(plan)
            if pc:
                print("      pacing: %d clips, %.2fs mean (%.2f-%.2fs), %s%s" % (
                    pc["clips"], pc["mean_s"], pc["min_s"], pc["max_s"],
                    "accelerating" if pc["accelerates"] else "not accelerating",
                    ", MONOTONE" if pc["monotone"] else ""))
        for e in errs:
            print("      - " + e)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
