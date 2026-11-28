#!/usr/bin/env python3
"""
contact_sheet.py — tile timestamped frames of a video into JPEG sheets for visual review.

Why: an agent can't watch video, but it can read ONE image holding 12 timestamped frames
for ~1/10 the tokens of 12 separate frames. Use it two ways:
  * footage review : coarse overview (--interval 5), then dense windows (--interval 1 --start/--end)
  * draft QC       : render the reel, sheet it at --interval 0.5, look for dead/dark/repeated
                     shots, bad framing, and an abrupt ending BEFORE telling the user it is done.

  python3 contact_sheet.py VIDEO OUTDIR [--interval 1] [--start S] [--end E]
                           [--cols 4] [--rows 3] [--thumb-w 270] [--prefix NAME]
Writes OUTDIR/<prefix>_NNN.jpg. Needs ffmpeg with drawtext (any common build).
"""
import argparse
import glob
import os
import subprocess
import sys

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("outdir")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between frames")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--thumb-w", type=int, default=270)
    ap.add_argument("--prefix", default="sheet")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    font = next((f for f in FONTS if os.path.exists(f)), None)
    # label = source timestamp of each frame (start offset + pts)
    label = ""
    if font:
        label = (f",drawtext=fontfile='{font}':text='%{{pts\\:hms\\:{a.start}}}':x=6:y=6:"
                 "fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6")
    vf = f"fps=1/{a.interval},scale={a.thumb_w}:-2{label},tile={a.cols}x{a.rows}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a.start)]
    if a.end is not None:
        cmd += ["-t", str(a.end - a.start)]
    cmd += ["-i", a.video, "-vf", vf, "-q:v", "3",
            os.path.join(a.outdir, f"{a.prefix}_%03d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr)
        sys.exit(r.returncode)
    files = sorted(glob.glob(os.path.join(a.outdir, f"{a.prefix}_*.jpg")))
    print("\n".join(files))


if __name__ == "__main__":
    main()
