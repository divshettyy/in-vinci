#!/usr/bin/env python3
"""Render a self-contained HTML timeline preview of a cut plan (stdlib only).

Shows each clip as a block on the timeline, the beat grid (shifted by the audio
start offset, same as validate_plans), the drop marker, and every cut's signed
offset from its nearest beat -- so you can eyeball sync without rendering.

Usage: python3 tools/preview_timeline.py [plans_dir] [-o out/timeline.html]
"""
import glob
import html
import json
import os
import sys

FPS = 30.0


def timeline_model(plan, beats, fps=FPS):
    """Pure data for the preview: clips, cuts, beat times, drop (all seconds)."""
    offset = float((plan.get("audio_add") or {}).get("sourceStartFromInSeconds", plan.get("phase", 0.0)) or 0.0)
    clips, acc = [], 0
    for a in plan.get("video_adds", []):
        d = int(a.get("durationInFrames", 0))
        clips.append({"start": acc / fps, "end": (acc + d) / fps, "frames": d})
        acc += d
    total = acc / fps
    bt = [round(b - offset, 3) for b in beats.get("beats", []) if 0 <= b - offset <= total]
    cuts = []
    for c in clips[:-1]:
        t = c["end"]
        near = min(bt, key=lambda b: abs(b - t)) if bt else None
        cuts.append({"t": t, "off_ms": None if near is None else round((t - near) * 1000, 1)})
    drop = beats.get("drop_time_beat", beats.get("drop_time"))
    drop = None if drop is None or not (0 <= drop - offset <= total) else round(drop - offset, 3)
    return {"total": total, "clips": clips, "cuts": cuts, "beats": bt, "drop": drop}


def render_plan(slug, m):
    W = 1000.0
    x = lambda t: t / m["total"] * W if m["total"] else 0
    parts = ['<svg viewBox="0 0 %d 90" width="100%%" role="img" aria-label="Timeline for %s">' % (W, html.escape(slug))]
    for t in m["beats"]:
        parts.append('<line x1="%.1f" x2="%.1f" y1="0" y2="20" stroke="#888" stroke-width="1"/>' % (x(t), x(t)))
    for i, c in enumerate(m["clips"]):
        fill = "#3b82f6" if i % 2 == 0 else "#6366f1"
        parts.append('<rect x="%.1f" y="26" width="%.1f" height="36" fill="%s"><title>clip %d: %d frames</title></rect>'
                     % (x(c["start"]), max(1, x(c["end"]) - x(c["start"]) - 1), fill, i + 1, c["frames"]))
    for c in m["cuts"]:
        bad = c["off_ms"] is not None and abs(c["off_ms"]) > 2 / FPS * 1000
        parts.append('<line x1="%.1f" x2="%.1f" y1="22" y2="66" stroke="%s" stroke-width="2"><title>cut %+.1f ms from beat</title></line>'
                     % (x(c["t"]), x(c["t"]), "#ef4444" if bad else "#22c55e", c["off_ms"] or 0))
    if m["drop"] is not None:
        parts.append('<polygon points="%.1f,70 %.1f,86 %.1f,86" fill="#f59e0b"><title>drop %.3fs</title></polygon>'
                     % (x(m["drop"]), x(m["drop"]) - 6, x(m["drop"]) + 6, m["drop"]))
    parts.append("</svg>")
    offs = [abs(c["off_ms"]) for c in m["cuts"] if c["off_ms"] is not None]
    stat = "%d clips &middot; %.1fs &middot; max cut offset %s ms" % (
        len(m["clips"]), m["total"], "%.0f" % max(offs) if offs else "n/a")
    return "<section><h2>%s</h2><p>%s</p>%s</section>" % (html.escape(slug), stat, "".join(parts))


def build(plans_dir):
    secs = []
    for p in sorted(glob.glob(os.path.join(plans_dir, "*.json"))):
        if p.endswith("_beats.json"):
            continue
        bp = p[:-5] + "_beats.json"
        if not os.path.exists(bp):
            continue
        with open(p, encoding="utf-8") as f:
            plan = json.load(f)
        with open(bp, encoding="utf-8") as f:
            beats = json.load(f)
        secs.append(render_plan(os.path.basename(p)[:-5], timeline_model(plan, beats)))
    return ("<!doctype html><meta charset=utf-8><title>in-vinci timelines</title>"
            "<style>body{font:14px system-ui;background:#111;color:#eee;margin:16px}"
            "section{margin-bottom:20px}h2{margin:0;font-size:16px}p{margin:2px 0 6px;color:#aaa}</style>"
            "<h1>Cut timelines</h1><p>grey ticks = beats, blocks = clips, green/red = cut on/off beat, amber = drop</p>"
            + "".join(secs))


def main(argv):
    out, args = "timeline.html", []
    it = iter(argv)
    for a in it:
        if a == "-o":
            out = next(it)
        else:
            args.append(a)
    d = args[0] if args else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plans")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(d))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
