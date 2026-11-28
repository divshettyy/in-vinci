---
name: reel-builder
description: >
  Build a trend-tuned vertical reel (IG Reels / TikTok / YT Shorts) from a folder of
  raw clips plus a music track, inside ChatCut. Objective shot detection + quality
  gate (auto-drops filler clips), beat-locked cuts, hook-first / energy-arc / loop-aware
  ordering, speed ramps on slow-mo, punch-in zoom on drops, optional kinetic captions,
  cloud export. Use when the user drops a clips folder + a track and wants a reel,
  montage, edit, "make it good / viral / trendy", beat-synced cut, or a short-form edit
  from raw footage. Triggers: reel, montage, edit my clips, beat sync, short form,
  shorts, tiktok, moto reel, highlight reel, make it trendy.
---

# reel-builder

Turns a folder of raw clips + one audio track into a beat-synced vertical reel in
ChatCut. A Python engine (`reel_engine.py`) does the objective analysis offline; you
(the agent) drive ChatCut over MCP to assemble and export. The engine never touches
the network and never edits the timeline.

## FOSS stack (why it's good)

The engine stands on the best free/open-source building blocks, each doing the one
job it's best at:

| Tool | License | Job in the pipeline |
|------|---------|---------------------|
| **ffmpeg / ffprobe** | LGPL/GPL | decode, probe, trim subclips, cut track windows, export |
| **PySceneDetect** | BSD-3 | real shot-boundary detection (cut on shot changes, trim dead frames) |
| **OpenCV** | Apache-2 | per-frame quality metrics — sharpness (var-of-Laplacian), exposure, motion → the filler-reject gate |
| **librosa** | ISC | tempo + beat grid + onset-strength "drop" detection |
| **numpy** | BSD | the math under all of it |

All optional accelerators degrade gracefully: no OpenCV/PySceneDetect → ffmpeg
frame-diff fallback (no quality gate); no librosa → numpy spectral-flux beat tracker.

### Install (one venv, already set up here)

```bash
cd ~/.claude/skills/reel-builder
python3 -m venv .venv
./.venv/bin/python -m pip install numpy opencv-python-headless scenedetect librosa soundfile
```

Run the engine with `./.venv/bin/python reel_engine.py ...`.

## Inputs to confirm first

- **clips dir** — folder of source videos (mp4/mov/m4v/webm/mkv).
- **audio track** — one local file. Beat-sync is the #1 quality lever; every trending
  moto/automotive reel is music-driven (verified via vidIQ outliers). ChatCut AI music
  needs Pro, so get a user track or a CC0 pick. Never fetch a copyrighted track off the web.
- **length** (default 18s — outlier sweet spot is 8–24s), **style**, **platform**
  (vertical 1080x1920 default).

Styles: `phonk` (fast 1–2 beat cuts, drop-forward — default for moto), `cinematic`
(4–8 beat holds, build), `lofi` (2–4 beat, smooth), `balanced`.

## Trend rules the plan encodes (2026 moto/automotive outliers)

1. **Beat drops on frame 1** — strongest action shot first, started on its motion peak.
   Cut the track window so the drop lands at/near t=0.
2. **Every cut on the beat** — cut lengths come straight off the detected beat grid.
3. **Energy arc** — fastest cuts cluster on the musical drop.
4. **Loop** — the tail cut differs from the hook clip so the loop point reads as motion.
5. **Music only** — mute the clips' embedded audio (`decibelAdjustment:-60`).
6. **Drop filler** — the quality gate rejects blurry+static / near-black / blown windows.

## Pipeline

### 1. Analyze + plan (engine, offline)

```bash
./.venv/bin/python reel_engine.py all \
  --clips "<CLIPS_DIR>" --audio "<TRACK>" \
  --length 18 --style phonk --timeline-fps 30 \
  --out-dir "<WORKDIR>"
```

Writes `clips.json` (per-clip shots + scored/gated windows), `beats.json` (tempo +
beat grid + drop_time), and `plan.json` (the hook-first, beat-locked, loop-aware cut
list). Run sub-commands (`analyze`, `beats`, `plan`) individually to iterate; re-running
`plan` is cheap, so try several `--style`/`--length` values without re-analyzing.

`plan.json` `cuts[]`: `clip`, `source_start_s`, `duration_frames` (at timeline fps),
`beat_time_s`, `score`, `effects[]` (`speed_ramp` / `punch_zoom` / `cover_crop`),
`landscape`. `cuts[0]` is the hook. `rejected[]` lists dropped windows + reason.

Key flags: `--scene-threshold` (lower = more shots), `--static-pct` / `--blur-pct`
(gate aggressiveness), `--luma-floor/--luma-ceil` (exposure reject), `--max-uses`
(per-clip reuse cap), `--claims claims.json` (making several reels from one footage
pool: ranges already used are skipped and this reel's ranges appended, so no source second
repeats across the set), `--no-zoom` (drop every `punch_zoom`), `--ending loop|fade`
(`fade` = held last frame + 0.7s video/audio fade-out, recorded in `plan.json` `ending`).

### 2. Prep source in ChatCut

- Create or target a project; set the timeline to 9:16 (`manage_timelines` update
  `ratio:"9:16"`, `fit:"cover"`).
- Get clip bytes local for analysis. If they live only as ChatCut assets, pull them
  with `request_asset_download` (needs a signed-in browser cookie — see
  `download_clips.sh` pattern in the workdir) or re-upload originals.
- Upload the track with the `asset-import` upload-helper (headless, no browser):
  `import_media action:create_session` → `upload-media.mjs`.
- `browse_assets` → map each `clip` filename to its `assetId`.

### 3. Build the timeline from the plan

For each cut in order, one `edit_item` add (sequential via `alignTo:"track-end"`):

- `assetId` = mapped id, `durationInFrames` = `duration_frames`,
  `sourceStartFromInSeconds` = `source_start_s` (recompute if you trimmed subclips).
- `cover_crop` → `fit:"cover"` (landscape source in vertical frame).
- `speed_ramp` → slow-mo (120fps) source: `playbackRate` ≈ 0.5, or leave native + keep short.
- `punch_zoom` → on drop hits, scale the item ~1.08× centered. Keep subtle.

Cuts land on `beat_time_s` because `duration_frames` sums the beat spacing — place them
back-to-back on one track and the cuts fall on the beat.

### 4. Audio + finish

- Add the track as an audio item on A1 from `sourceStartFromInSeconds:0`, trimmed to the
  video length, with a short `audioFadeOut`.
- Mute the clips' embedded audio (`decibelAdjustment:-60`) — music only.
- Captions optional (on-trend for sound-off); this footage is ambient so usually skip
  or add short hook text.

### 5. Verify + export

- Verify composed frames with `preview_timeline views:["viewer"]` when a browser
  executor is connected; otherwise state that visual check needs the editor open.
- Export: `submit_export`. Local render needs a connected editor tab; headless → use
  `renderMode:"cloud"` (quote first — often free), then download the `downloadUrl`.

## Review before you say "done" (ported from a parallel ride-reel pipeline, 2026-11-28)

Scores and gates find flaws; they do not judge taste. Before telling the user a reel is ready:

1. **Look at the draft yourself.** Export, then `python3 contact_sheet.py reel.mp4 qc --interval 0.5`
   and read the sheets. Check: hook shot is strong on frame 1, no near-black / empty /
   head-turn / mirror-edge frames, no repeated shot, middle does not sag, last 3 s are framed
   well and the ending is planned (not a mid-motion chop unless it is a deliberate loop).
   Send weak cuts back (rebuild `plan` with another `--style`/`--length`) instead of shipping.
2. **Footage first, music second.** For a set of reels, review the raw footage once
   (`contact_sheet.py` coarse overview `--interval 5`, then dense `--interval 1` windows), note
   the best moments, and let the story pick shots; the beat grid fits cuts to them.
   Do not let the track or the score become the goal.
3. **Use critics to catch flaws, not to rebuild.** A checklist rebuild once made reels worse than
   the originals because the rules removed the good moments. Hard thresholds are warnings.
4. **Plan the ending.** Loop reels: tail differs from hook. Non-looping: `--ending fade`.
5. **Deliver two files:** with music, and a silent copy (`ffmpeg -i in.mp4 -map 0:v:0 -c:v copy -an silent.mp4`)
   for adding a trending track inside Instagram, plus the exact in-app start time of the track
   window. Rights of the track are unknown unless the user owns it.
6. **Verify the render is current** (plan file older than the output) before announcing it, and keep QC
   frames out of the deliverables folder.
7. **Ask what they liked.** After delivery ask which reel and moment worked, and save that as taste
   memory. Taste is per user: some viewers hate zoom, grading and on-screen text (use `--no-zoom`),
   so check the stored preference first instead of assuming the defaults.

Machine tips: decode 4K one job at a time with hardware decode (`-hwaccel auto`), analyse
720p proxies, never edit or delete originals, and keep Python media packages pinned if a
transcriber breaks (`av<19` with faster-whisper).

## Notes / gotchas

- Rotation: phone-vertical clips are coded 1920x1080 with rotation -90; ffprobe shows
  coded dims, ChatCut shows displayed (1080x1920). The engine reports `display_vertical`;
  trust it over raw width/height.
- No browser executor connected → no viewer-frame verify and no local export; cloud
  export still works, and `edit_item` timeline building works regardless.
- Beat detection: librosa is accurate but can land on half/double time; the engine
  octave-folds into 70–155 BPM and rebuilds an even grid. For variable-tempo tracks,
  hand-tune `--length` or cut the track window around the drop.
- `plan` is deterministic given the same inputs; tweak `--style`/`--length` and rebuild
  rather than hand-editing `plan.json`.
- Keep subclips, the track window, and engine output in a workdir, not the clips folder.
- `reel_engine_v1_backup.py` is the pre-v2 engine (motion-only, no quality gate).
