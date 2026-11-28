#!/usr/bin/env python3
"""
reel_engine.py (v2) — offline analysis engine for trend-tuned vertical reels.

Pipeline (offline; ffmpeg + numpy required. OpenCV + PySceneDetect + librosa used
when importable, with numpy/ffmpeg fallbacks so the engine still runs without them):

  analyze : per-clip shot detection + quality/action scoring  -> clips.json
  beats   : tempo + beat grid + drop/onset envelope of a track -> beats.json
  plan    : combine peaks + beats + style -> hook-first, beat- -> plan.json
            locked, energy-arced, loop-aware cut list
  all     : run the three in sequence

plan.json is consumed by the reel-builder SKILL, which maps clip filenames to
ChatCut asset ids and assembles the timeline over MCP. This engine never touches
the network and never edits the timeline itself.

What v2 adds over v1:
  * PySceneDetect shot boundaries (cut on real shot changes; trim dead frames).
  * OpenCV per-frame quality metrics: sharpness (variance of Laplacian),
    exposure (luma + clipping), motion. A quality gate auto-REJECTS filler
    (blurry+static, near-black, blown-out) with a recorded reason, so weak clips
    drop out instead of landing in the reel.
  * librosa beat tracking + onset-strength "drop" detection (hook/arc anchor).
  * Ordering: strongest shot as an instant-action hook on frame 1, energy arc
    that lands the fastest cuts on the musical drop, and a loop-aware final cut.

Usage:
  python3 reel_engine.py analyze --clips DIR --out clips.json
  python3 reel_engine.py beats   --audio TRACK --out beats.json
  python3 reel_engine.py plan    --clips clips.json --beats beats.json \
          --length 18 --style phonk --timeline-fps 30 --out plan.json
  python3 reel_engine.py all     --clips DIR --audio TRACK --length 18 \
          --style phonk --out-dir OUTDIR

Styles: phonk | cinematic | lofi | balanced  (cut length + ordering curve).
"""
import argparse
import json
import math
import os
import subprocess
import sys

try:
    import numpy as np
except ImportError:
    sys.stderr.write("ERROR: numpy is required (pip install numpy)\n")
    sys.exit(2)

# Optional accelerators — degrade gracefully if absent.
try:
    import cv2
    _HAVE_CV2 = True
except Exception:
    _HAVE_CV2 = False

try:
    from scenedetect import detect, ContentDetector
    _HAVE_SCENEDETECT = True
except Exception:
    _HAVE_SCENEDETECT = False

VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi")


# ----------------------------------------------------------------------------- utils
def run(cmd):
    return subprocess.run(cmd, capture_output=True)


def ffprobe_json(path):
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", path,
    ]
    p = run(cmd)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


def probe_video(path):
    info = ffprobe_json(path)
    if not info:
        return None
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        return None
    dur = None
    try:
        dur = float(info.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        pass
    if dur is None:
        try:
            dur = float(v.get("duration"))
        except (TypeError, ValueError):
            dur = 0.0
    fps = 30.0
    rate = v.get("r_frame_rate") or v.get("avg_frame_rate") or "30/1"
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else 30.0
    except Exception:
        pass
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                rot = int(sd["rotation"])
            except (TypeError, ValueError):
                pass
    tags = v.get("tags", {}) or {}
    if not rot and "rotate" in tags:
        try:
            rot = int(tags["rotate"])
        except (TypeError, ValueError):
            pass
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    disp_vertical = ((abs(rot) % 180) == 90 and w >= h) or (h > w)
    return {
        "duration": round(dur, 3),
        "fps": round(fps, 3),
        "rotation": rot,
        "coded_w": w,
        "coded_h": h,
        "display_vertical": bool(disp_vertical),
        "slowmo": fps >= 90.0,  # 120fps source = slow-mo candidate
    }


# ------------------------------------------------------------------- shot detection
def detect_shots(path, threshold, min_scene_s, duration, fps):
    """Return a list of (start_s, end_s) shots. Falls back to [whole clip]."""
    if _HAVE_SCENEDETECT:
        try:
            min_len = max(1, int(round(min_scene_s * (fps or 30.0))))
            scenes = detect(path, ContentDetector(threshold=threshold, min_scene_len=min_len))
            shots = [(float(s.get_seconds()), float(e.get_seconds())) for s, e in scenes]
            shots = [(s, e) for s, e in shots if e - s > 0.05]
            if shots:
                return shots
        except Exception as e:
            sys.stderr.write(f"[analyze] scenedetect failed on {os.path.basename(path)}: {e}\n")
    if duration and duration > 0:
        return [(0.0, float(duration))]
    return []


# ------------------------------------------------------------------- frame metrics
def sample_metrics_cv2(path, sample_fps, width):
    """Decode with OpenCV, return dict of per-sample numpy arrays:
       t, motion (mean abs gray diff), sharp (var of Laplacian), luma (mean).
       Returns None if OpenCV cannot open the file."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    native = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if native <= 0:
        native = 30.0
    stride = max(1, int(round(native / float(sample_fps))))
    ts, motion, sharp, luma = [], [], [], []
    prev = None
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % stride == 0:
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                idx += 1
                continue
            h0, w0 = frame.shape[:2]
            if w0 > width:
                scale = width / float(w0)
                frame = cv2.resize(frame, (width, max(1, int(h0 * scale))),
                                   interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            g = gray.astype(np.float32)
            luma.append(float(g.mean()))
            sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            if prev is not None:
                motion.append(float(np.abs(g - prev).mean()))
            else:
                motion.append(0.0)
            prev = g
            ts.append(idx / native)
        idx += 1
    cap.release()
    if len(ts) < 2:
        return None
    return {
        "t": np.asarray(ts, dtype=np.float32),
        "motion": np.asarray(motion, dtype=np.float32),
        "sharp": np.asarray(sharp, dtype=np.float32),
        "luma": np.asarray(luma, dtype=np.float32),
    }


def sample_metrics_ffmpeg(path, sample_fps, width, height):
    """Fallback: decode downscaled gray via ffmpeg; motion + luma only
       (no sharpness without OpenCV; sharp filled with NaN)."""
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", path,
        "-vf", f"fps={sample_fps},scale={width}:{height},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout:
        return None
    fb = width * height
    n = len(p.stdout) // fb
    if n < 2:
        return None
    arr = np.frombuffer(p.stdout[: n * fb], dtype=np.uint8).reshape(n, height, width).astype(np.float32)
    luma = arr.mean(axis=(1, 2))
    diff = np.abs(arr[1:] - arr[:-1]).mean(axis=(1, 2))
    motion = np.concatenate([[0.0], diff])
    t = np.arange(n, dtype=np.float32) / float(sample_fps)
    sharp = np.full(n, np.nan, dtype=np.float32)
    return {"t": t, "motion": motion, "sharp": sharp, "luma": luma}


# ------------------------------------------------------------------------- analyze
def _window_stats(m, i0, i1):
    """Aggregate metric arrays over sample index range [i0, i1)."""
    sl = slice(i0, i1)
    mo = m["motion"][sl]
    sh = m["sharp"][sl]
    lu = m["luma"][sl]
    if mo.size == 0:
        return None
    sharp_med = float(np.nanmedian(sh)) if np.isfinite(sh).any() else float("nan")
    peak_i = i0 + int(np.argmax(mo)) if mo.size else i0
    return {
        "motion": float(mo.mean()),
        "motion_std": float(mo.std()),
        "sharp": sharp_med,
        "luma": float(lu.mean()),
        "peak_t": float(m["t"][min(peak_i, len(m["t"]) - 1)]),
    }


def analyze_clip(path, args):
    meta = probe_video(path)
    if not meta:
        return None
    dur = meta["duration"]
    fps = meta["fps"]

    m = None
    if _HAVE_CV2:
        m = sample_metrics_cv2(path, args.sample_fps, args.width)
    if m is None:
        h = max(2, int(round(args.width * 9 / 16)))
        m = sample_metrics_ffmpeg(path, args.sample_fps, args.width, h)
    if m is None:
        meta["windows"] = []
        meta["error"] = "decode_failed"
        return meta

    shots = detect_shots(path, args.scene_threshold, args.min_scene_s, dur, fps)
    meta["shot_count"] = len(shots)

    t = m["t"]
    win_s = args.window_s
    windows = []
    for si, (s0, s1) in enumerate(shots):
        # clamp shot to sampled range
        i0 = int(np.searchsorted(t, s0, side="left"))
        i1 = int(np.searchsorted(t, s1, side="right"))
        if i1 - i0 < 2:
            continue
        shot_len = s1 - s0
        # slide a window across the shot; step half a window
        wn = max(2, int(round(win_s * args.sample_fps)))
        step = max(1, wn // 2)
        if i1 - i0 <= wn:  # shot shorter than a window: one window = whole shot
            spans = [(i0, i1)]
        else:
            spans = [(j, min(j + wn, i1)) for j in range(i0, i1 - 1, step)]
        for (j0, j1) in spans:
            st = _window_stats(m, j0, j1)
            if not st:
                continue
            windows.append({
                "shot": si,
                "start": round(float(t[j0]), 3),
                "end": round(float(t[min(j1, len(t) - 1)]), 3),
                "peak": round(st["peak_t"], 3),
                "motion": round(st["motion"], 4),
                "motion_std": round(st["motion_std"], 4),
                "sharp": None if math.isnan(st["sharp"]) else round(st["sharp"], 2),
                "luma": round(st["luma"], 2),
                "shot_len": round(shot_len, 3),
            })
    meta["windows"] = windows
    meta["motion_mean"] = round(float(m["motion"].mean()), 4)
    meta["luma_mean"] = round(float(m["luma"].mean()), 2)
    if np.isfinite(m["sharp"]).any():
        meta["sharp_mean"] = round(float(np.nanmean(m["sharp"])), 2)
    return meta


def cmd_analyze(args):
    files = sorted(
        f for f in os.listdir(args.clips)
        if f.lower().endswith(VIDEO_EXT) and os.path.isfile(os.path.join(args.clips, f))
    )
    if not files:
        sys.stderr.write(f"No video files in {args.clips}\n")
        sys.exit(1)
    clips = {}
    for name in files:
        path = os.path.join(args.clips, name)
        sys.stderr.write(f"[analyze] {name} ... ")
        sys.stderr.flush()
        res = analyze_clip(path, args)
        if res is None:
            sys.stderr.write("skip (probe failed)\n")
            continue
        clips[name] = res
        sys.stderr.write(
            f"{res.get('shot_count', 0)} shots, {len(res.get('windows', []))} windows, "
            f"motion~{res.get('motion_mean', 0)}, sharp~{res.get('sharp_mean', 'n/a')}\n"
        )
    out = {
        "sample_fps": args.sample_fps,
        "width": args.width,
        "have_cv2": _HAVE_CV2,
        "have_scenedetect": _HAVE_SCENEDETECT,
        "clips": clips,
    }
    _write(args.out, out)
    sys.stderr.write(f"[analyze] wrote {args.out} ({len(clips)} clips)\n")


# --------------------------------------------------------------------------- beats
def decode_audio_mono(path, sr=22050):
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", path,
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
    ]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout:
        return None
    return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def beats_librosa(path):
    try:
        import librosa
    except ImportError:
        return None
    try:
        y, sr = librosa.load(path, sr=22050, mono=True)
        tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
        times = librosa.frames_to_time(frames, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])
        # onset strength envelope -> locate the drop (max sustained onset energy)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        oe_times = librosa.times_like(onset_env, sr=sr)
        return {
            "tempo": round(tempo, 2),
            "beats": [round(float(t), 3) for t in times],
            "onset_env": onset_env,
            "onset_times": oe_times,
            "source": "librosa",
        }
    except Exception as e:
        sys.stderr.write(f"[beats] librosa failed ({e}); falling back\n")
        return None


def beats_fallback(path, sr=22050):
    x = decode_audio_mono(path, sr)
    if x is None or x.size < sr:
        return None
    hop, win = 512, 1024
    n_frames = 1 + (len(x) - win) // hop if len(x) >= win else 0
    if n_frames < 8:
        return None
    window = np.hanning(win).astype(np.float32)
    prev = np.zeros(win // 2 + 1, dtype=np.float32)
    flux = np.empty(n_frames, dtype=np.float32)
    for i in range(n_frames):
        seg = x[i * hop: i * hop + win] * window
        mag = np.abs(np.fft.rfft(seg))
        d = mag - prev
        flux[i] = np.sum(d[d > 0])
        prev = mag
    env = flux.copy()
    flux -= flux.mean()
    flux[flux < 0] = 0
    if flux.max() > 0:
        flux /= flux.max()
    fps_env = sr / hop
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    lag_min = int(fps_env * 60.0 / 200.0)
    lag_max = min(int(fps_env * 60.0 / 60.0), len(ac) - 1)
    if lag_max <= lag_min:
        return None
    lag = lag_min + int(np.argmax(ac[lag_min: lag_max + 1]))
    period = lag / fps_env
    tempo = 60.0 / period if period > 0 else 120.0
    first_region = flux[: max(1, int(fps_env * period))]
    start_idx = int(np.argmax(first_region)) if first_region.size else 0
    start_t = start_idx / fps_env
    total = len(x) / sr
    beats, t = [], start_t
    while t < total:
        beats.append(round(float(t), 3))
        t += period
    oe_times = np.arange(len(env)) / fps_env
    return {"tempo": round(float(tempo), 2), "beats": beats,
            "onset_env": env, "onset_times": oe_times, "source": "fallback"}


def fold_tempo(tempo, lo=70.0, hi=155.0):
    if tempo <= 0:
        return 120.0
    while tempo > hi:
        tempo /= 2.0
    while tempo < lo:
        tempo *= 2.0
    return tempo


def _find_drop(onset_env, onset_times, duration):
    """Estimate the drop time: the strongest sustained rise in onset energy,
       searched after a short intro and before the last few seconds."""
    if onset_env is None or len(onset_env) < 4:
        return None
    env = np.asarray(onset_env, dtype=np.float32)
    tt = np.asarray(onset_times, dtype=np.float32)
    if env.max() > 0:
        env = env / env.max()
    lo_t = min(2.0, duration * 0.1) if duration else 2.0
    hi_t = (duration - 1.5) if duration else tt[-1]
    mask = (tt >= lo_t) & (tt <= hi_t)
    if not mask.any():
        return float(tt[int(np.argmax(env))])
    idx = np.where(mask)[0]
    # smooth, then take the max-energy region as the drop anchor
    k = max(1, int(round(len(env) / max(1.0, (tt[-1] or 1.0)) * 0.5)))  # ~0.5s smoothing
    if k > 1:
        kern = np.ones(k) / k
        sm = np.convolve(env, kern, mode="same")
    else:
        sm = env
    j = idx[int(np.argmax(sm[idx]))]
    return round(float(tt[j]), 3)


def cmd_beats(args):
    res = beats_librosa(args.audio) or beats_fallback(args.audio)
    if not res:
        sys.stderr.write("[beats] could not analyze audio\n")
        sys.exit(1)
    dur = 0.0
    info = ffprobe_json(args.audio)
    if info:
        try:
            dur = float(info.get("format", {}).get("duration"))
        except (TypeError, ValueError):
            pass
    res["duration"] = round(dur, 3)

    drop = _find_drop(res.get("onset_env"), res.get("onset_times"), dur)

    raw_tempo = res.get("tempo", 120.0)
    folded = fold_tempo(raw_tempo)
    if dur > 0 and folded > 0:
        period = 60.0 / folded
        start = res["beats"][0] if res.get("beats") else 0.0
        while start - period >= 0:
            start -= period
        grid, t = [], start
        while t < dur:
            if t >= 0:
                grid.append(round(float(t), 3))
            t += period
        res["beats"] = grid
    res["tempo_raw"] = round(float(raw_tempo), 2)
    res["tempo"] = round(float(folded), 2)
    res["drop_time"] = drop
    # strip heavy arrays before writing
    res.pop("onset_env", None)
    res.pop("onset_times", None)
    _write(args.out, res)
    sys.stderr.write(
        f"[beats] tempo={res['tempo']} BPM (raw {res['tempo_raw']}), "
        f"{len(res['beats'])} beats, drop~{drop}s ({res['source']}) -> {args.out}\n"
    )


# ---------------------------------------------------------------------------- plan
STYLE = {
    "phonk":     {"cut_beats": [2, 2, 1], "drop_beats": [1, 1],    "min_cut_s": 0.33,
                  "hook_beats": 2, "arc": "drop"},
    "cinematic": {"cut_beats": [8, 4],    "drop_beats": [4],       "min_cut_s": 1.3,
                  "hook_beats": 4, "arc": "build"},
    "lofi":      {"cut_beats": [4, 2],    "drop_beats": [2],       "min_cut_s": 0.8,
                  "hook_beats": 4, "arc": "smooth"},
    "balanced":  {"cut_beats": [2, 2, 4], "drop_beats": [2, 1],    "min_cut_s": 0.5,
                  "hook_beats": 2, "arc": "build"},
}


def _load_claims(path):
    """Footage-claim registry: {clip: [[start, end], ...]} of source ranges already used
    by earlier reels in the same set, so no source second repeats across reels."""
    if not path or not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def _claimed(claims, clip, a, b):
    return any(a < e and b > s for s, e in claims.get(clip, []))


def _percentile(vals, q):
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], dtype=np.float32)
    if a.size == 0:
        return None
    return float(np.percentile(a, q))


def _gate_and_score(cand, args):
    """Apply the quality gate (mark rejects + reason) and compute a final score.
       Scores normalized across the whole candidate pool so clips are comparable."""
    motions = [c["motion"] for c in cand]
    sharps = [c["sharp"] for c in cand if c["sharp"] is not None]
    mo_lo = _percentile(motions, args.static_pct) or 0.0
    sh_lo = _percentile(sharps, args.blur_pct) if sharps else None
    mo_max = max(motions) if motions else 1.0
    sh_vals = [c["sharp"] for c in cand if c["sharp"] is not None]
    sh_max = max(sh_vals) if sh_vals else 1.0

    for c in cand:
        reasons = []
        # near-black / blown-out (hard reject)
        if c["luma"] < args.luma_floor:
            reasons.append("too_dark")
        if c["luma"] > args.luma_ceil:
            reasons.append("too_bright")
        # blurry AND static = true filler (hard reject). Motion-blur action survives.
        blurry = (c["sharp"] is not None and sh_lo is not None and c["sharp"] < sh_lo)
        static = c["motion"] < mo_lo
        if blurry and static:
            reasons.append("blurry_static")
        c["reject"] = bool(reasons)
        c["reject_reason"] = ",".join(reasons) if reasons else None

        # composite score: action (normalized motion) * quality (sharp) * exposure_ok
        a = c["motion"] / mo_max if mo_max > 0 else 0.0
        if c["sharp"] is not None and sh_max > 0:
            q = 0.5 + 0.5 * min(1.0, c["sharp"] / sh_max)   # 0.5..1.0
        else:
            q = 0.8
        # mild exposure preference (dark night ok, but reward midtones a touch)
        ex = 1.0
        if c["luma"] < args.luma_floor * 2:
            ex = 0.85
        vert = 1.0 if c.get("display_vertical", True) else 0.82
        # shake penalty: very jittery windows (high motion variance vs mean) lose a little
        jit = 1.0
        if c["motion"] > 0 and c.get("motion_std", 0) / max(c["motion"], 1e-6) > 2.2:
            jit = 0.9
        c["score"] = round(float(a * q * ex * vert * jit), 4)
        c["action"] = round(float(a), 4)
    return cand


def cmd_plan(args):
    with open(args.clips) as fh:
        clips_doc = json.load(fh)
    with open(args.beats) as fh:
        beats_doc = json.load(fh)
    clips = clips_doc.get("clips", {})
    beats = beats_doc.get("beats", [])
    tempo = beats_doc.get("tempo", 120.0)
    drop_time = beats_doc.get("drop_time")
    style = STYLE.get(args.style, STYLE["balanced"])
    tfps = args.timeline_fps
    claims = _load_claims(getattr(args, "claims", None))
    no_zoom = getattr(args, "no_zoom", False)
    ending = getattr(args, "ending", "loop")

    if len(beats) < 4:
        period = 60.0 / (tempo or 120.0)
        beats = [round(i * period, 3) for i in range(int(args.length / period) + 4)]

    # nearest beat index to the drop
    drop_bi = None
    if drop_time is not None and beats:
        drop_bi = int(np.argmin([abs(b - drop_time) for b in beats]))

    # flatten candidate windows
    cand = []
    for name, c in clips.items():
        vert = c.get("display_vertical", True)
        for w in c.get("windows", []):
            cand.append({
                "clip": name,
                "src_start": w["start"],
                "peak": w["peak"],
                "motion": w["motion"],
                "motion_std": w.get("motion_std", 0.0),
                "sharp": w.get("sharp"),
                "luma": w["luma"],
                "slowmo": c.get("slowmo", False),
                "display_vertical": vert,
                "shot": w.get("shot", 0),
                "src_dur": max(0.0, c.get("duration", 0) - w["start"]),
            })
    if not cand:
        sys.stderr.write("[plan] no candidate windows; run analyze first\n")
        sys.exit(1)

    cand = _gate_and_score(cand, args)
    pool = [c for c in cand if not c["reject"]]
    rejected = [c for c in cand if c["reject"]]
    if not pool:  # gate too strict for this footage; fall back to full pool
        pool = cand
    for i, c in enumerate(pool):
        c["_key"] = (c["clip"], round(c["src_start"], 2))
    pool.sort(key=lambda x: x["score"], reverse=True)

    # ---- walk the beat grid, emitting cuts until target length ----
    target = float(args.length)
    plan = []
    used_recent = []
    used_keys = set()
    uses = {}
    bi = 0
    pos_s = 0.0
    idx = 0

    def pick_window(cut_s, allow_reuse):
        for c in pool:
            if c["_key"] in used_keys:
                continue
            if not allow_reuse and uses.get(c["clip"], 0) >= args.max_uses:
                continue
            if used_recent[-1:] == [c["clip"]]:
                continue
            need = cut_s * (0.25 if c["slowmo"] else 0.85)
            if c["src_dur"] < need:
                continue
            if claims:
                # check the range the cut will really use (peak-aligned start, slow-mo takes half)
                take = cut_s * (0.5 if c["slowmo"] else 1.0)
                lo = max(c["src_start"], c["peak"] - take * 0.35)
                if _claimed(claims, c["clip"], lo, lo + take):
                    continue
            return c
        return None

    while pos_s < target and bi < len(beats) - 1:
        # choose cut length in beats: faster near/at the drop (energy arc)
        near_drop = drop_bi is not None and abs(bi - drop_bi) <= 2
        patt = style["drop_beats"] if near_drop else style["cut_beats"]
        nbeats = patt[idx % len(patt)]
        idx += 1
        nb = min(nbeats, len(beats) - 1 - bi)
        if nb <= 0:
            break
        cut_s = beats[bi + nb] - beats[bi]
        if cut_s <= 0:
            cut_s = 60.0 / (tempo or 120.0) * nb
        cut_s = max(cut_s, style["min_cut_s"])

        pick = pick_window(cut_s, allow_reuse=False) or pick_window(cut_s, allow_reuse=True)
        if pick is None:
            break
        used_keys.add(pick["_key"])
        uses[pick["clip"]] = uses.get(pick["clip"], 0) + 1

        # start source so the action PEAK lands early in the cut (instant energy)
        if pick["slowmo"]:
            src_take = cut_s * 0.5
        else:
            src_take = cut_s
        src_start = max(pick["src_start"], pick["peak"] - src_take * 0.35)
        dur_frames = max(1, int(round(cut_s * tfps)))
        effects = []
        if pick["slowmo"]:
            effects.append("speed_ramp")
        if (nb <= 1 or near_drop) and not no_zoom:
            effects.append("punch_zoom")
        if not pick["display_vertical"]:
            effects.append("cover_crop")
        plan.append({
            "order": len(plan),
            "clip": pick["clip"],
            "source_start_s": round(src_start, 3),
            "duration_frames": dur_frames,
            "beats": nb,
            "beat_time_s": round(beats[bi], 3),
            "score": pick["score"],
            "effects": effects,
            "landscape": not pick["display_vertical"],
        })
        used_recent.append(pick["clip"])
        pos_s += cut_s
        bi += nb

    if not plan:
        sys.stderr.write("[plan] could not place any cut\n")
        sys.exit(1)

    # ---- hook: strongest vertical cut to the front, started on its peak ----
    def _best_hook(i):
        e = plan[i]
        base = e.get("score", 0)
        return base * (1.0 if not e["landscape"] else 0.82)
    best_i = max(range(len(plan)), key=_best_hook)
    if best_i != 0:
        plan.insert(0, plan.pop(best_i))

    # ---- loop-aware tail: make the last cut a high-motion shot unlike the hook,
    # so the jump back to the hook reads as momentum, not a stop.
    hook_clip = plan[0]["clip"]
    if ending == "loop" and len(plan) > 2 and plan[-1]["clip"] == hook_clip:
        for j in range(len(plan) - 2, 0, -1):
            if plan[j]["clip"] != hook_clip:
                plan[-1], plan[j] = plan[j], plan[-1]
                break

    for i, e in enumerate(plan):
        e["order"] = i

    if getattr(args, "claims", None):
        for e in plan:
            span = (e["duration_frames"] / tfps) * (0.5 if "speed_ramp" in e["effects"] else 1.0)
            claims.setdefault(e["clip"], []).append(
                [e["source_start_s"], round(e["source_start_s"] + span, 3)])
        _write(args.claims, claims)

    if ending == "fade":
        # planned ending: hold the last composed frame, then fade video (and audio) out.
        ending_doc = {"type": "fade", "fade_out_s": 0.7, "audio_fade_out_s": 0.7,
                      "note": "last cut ends the reel; do not hard-stop mid-motion"}
    else:
        ending_doc = {"type": "loop",
                      "note": "tail cut differs from hook clip so the loop reads as motion"}

    doc = {
        "style": args.style,
        "tempo": tempo,
        "drop_time": drop_time,
        "timeline_fps": tfps,
        "target_length_s": target,
        "planned_length_s": round(pos_s, 2),
        "cut_count": len(plan),
        "ending": ending_doc,
        "no_zoom": no_zoom,
        "pool_size": len(pool),
        "rejected": [
            {"clip": c["clip"], "src_start": c["src_start"], "reason": c["reject_reason"]}
            for c in rejected
        ],
        "cuts": plan,
        "notes": {
            "hook": "cut 0 is the strongest action window, started on its peak for frame-1 energy",
            "drop_sync": f"fastest cuts cluster around drop_time={drop_time}s",
            "loop": "tail cut differs from hook clip so the loop point reads as motion",
            "speed_ramp": "slow-mo (120fps) source; in ChatCut set playbackRate≈0.5 or trim tight",
            "punch_zoom": "small scale-in (1.0->1.08) via item width/height on hard hits",
            "cover_crop": "landscape source in vertical timeline; use fit:cover",
        },
    }
    _write(args.out, doc)
    sys.stderr.write(
        f"[plan] {len(plan)} cuts, ~{doc['planned_length_s']}s @ {tempo} BPM "
        f"({args.style}); pool={len(pool)} rejected={len(rejected)} -> {args.out}\n"
    )


def _write(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------------- all
def cmd_all(args):
    os.makedirs(args.out_dir, exist_ok=True)
    clips_json = os.path.join(args.out_dir, "clips.json")
    beats_json = os.path.join(args.out_dir, "beats.json")
    plan_json = os.path.join(args.out_dir, "plan.json")
    cmd_analyze(argparse.Namespace(
        clips=args.clips, out=clips_json, sample_fps=args.sample_fps, width=args.width,
        scene_threshold=args.scene_threshold, min_scene_s=args.min_scene_s,
        window_s=args.window_s))
    cmd_beats(argparse.Namespace(audio=args.audio, out=beats_json))
    cmd_plan(argparse.Namespace(
        clips=clips_json, beats=beats_json, length=args.length, style=args.style,
        timeline_fps=args.timeline_fps, max_uses=args.max_uses,
        static_pct=args.static_pct, blur_pct=args.blur_pct,
        luma_floor=args.luma_floor, luma_ceil=args.luma_ceil,
        claims=args.claims, no_zoom=args.no_zoom, ending=args.ending, out=plan_json))
    sys.stderr.write(f"[all] done -> {plan_json}\n")


# ----------------------------------------------------------------------------- cli
def _add_analyze_args(p):
    p.add_argument("--sample-fps", type=float, default=6.0,
                   help="frames/sec sampled for metrics")
    p.add_argument("--width", type=int, default=160, help="downscale width for metrics")
    p.add_argument("--scene-threshold", type=float, default=27.0,
                   help="PySceneDetect ContentDetector threshold (lower = more cuts)")
    p.add_argument("--min-scene-s", type=float, default=0.4, help="min shot length (s)")
    p.add_argument("--window-s", type=float, default=1.0, help="scoring window length (s)")


def _add_gate_args(p):
    p.add_argument("--max-uses", type=int, default=2,
                   help="max times one clip may appear before the cap relaxes")
    p.add_argument("--static-pct", type=float, default=20.0,
                   help="motion percentile below which a window counts as static")
    p.add_argument("--blur-pct", type=float, default=25.0,
                   help="sharpness percentile below which a window counts as blurry")
    p.add_argument("--luma-floor", type=float, default=6.0, help="reject near-black windows")
    p.add_argument("--luma-ceil", type=float, default=250.0, help="reject blown-out windows")
    p.add_argument("--claims", default=None,
                   help="JSON registry of source ranges already used; windows overlapping "
                        "it are skipped and this reel's ranges are appended (no repeated "
                        "footage across a set of reels)")
    p.add_argument("--no-zoom", action="store_true",
                   help="never emit punch_zoom (some audiences dislike any zoom/crop)")
    p.add_argument("--ending", choices=["loop", "fade"], default="loop",
                   help="loop = tail differs from hook (default); fade = held last frame "
                        "+ 0.7s video/audio fade-out, for non-looping reels")


def main():
    ap = argparse.ArgumentParser(description="Trend-tuned reel analysis engine (v2)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="shot detection + quality/action scoring")
    a.add_argument("--clips", required=True)
    a.add_argument("--out", required=True)
    _add_analyze_args(a)
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("beats", help="detect tempo + beat grid + drop")
    b.add_argument("--audio", required=True)
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_beats)

    p = sub.add_parser("plan", help="build a hook-first, beat-locked, loop-aware cut plan")
    p.add_argument("--clips", required=True)
    p.add_argument("--beats", required=True)
    p.add_argument("--length", type=float, default=18.0)
    p.add_argument("--style", default="phonk", choices=list(STYLE.keys()))
    p.add_argument("--timeline-fps", type=int, default=30)
    _add_gate_args(p)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_plan)

    al = sub.add_parser("all", help="analyze + beats + plan")
    al.add_argument("--clips", required=True)
    al.add_argument("--audio", required=True)
    al.add_argument("--length", type=float, default=18.0)
    al.add_argument("--style", default="phonk", choices=list(STYLE.keys()))
    al.add_argument("--timeline-fps", type=int, default=30)
    _add_analyze_args(al)
    _add_gate_args(al)
    al.add_argument("--out-dir", required=True)
    al.set_defaults(func=cmd_all)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
