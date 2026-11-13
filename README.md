# in-vinci — beat-synced phonk moto reel maker

Pipeline that turns slowed-phonk tracks + vertical moto source clips into
9:16 Instagram reels with cuts aligned to detected beats.

## Flow
1. **Beat detection** — librosa analyses each track; tempo + beat times saved to `beats/` and `plans/<slug>_beats.json` (also `beats_santafe.json` sample).
2. **Window cut** — ~19s hook window of each track exported to `windows/<slug>_19s.mp3`.
3. **Clip analysis** — source clips profiled in `clip_analysis/clips.json`.
4. **Cut plan** — `plans/<slug>.json`: beat-aligned `video_adds` (asset id, in-point, duration in frames, 9:16 crop/offset, audio muted to -60dB).
5. **Render** — plan + track window composited to the final reel.

## Requirements
- `bash`, `curl` — for `download_clips.sh` (the only committed script)
- `ffmpeg` — audio window export / final render muxing
- Python 3 + `librosa` — beat detection (external step, not committed here)
- `opencv-python` + `scenedetect` — source clip profiling (external step; see `clip_analysis/clips.json` output, produced with `have_cv2`/`have_scenedetect` flags)
- A ChatCut account + an active browser session (for the cookie used by `download_clips.sh`, and for the final composite render)

## Source clips
Not committed (`clips/` is gitignored). Re-fetch from ChatCut:
```bash
echo 'PASTE_CHATCUT_COOKIE' > cookie.txt   # one line, never committed
bash download_clips.sh
```
17 asset UUIDs + project id live in `download_clips.sh`. The cookie is your
raw ChatCut session cookie (see the script's header comment for how to copy
it from DevTools); it is read from `cookie.txt` at runtime and is never
hardcoded or committed — `cookie.txt` is gitignored.

No other secrets or environment variables are required by anything in this
repo.

## Layout
- `plans/` — per-track cut plans + beat maps
- `beats/` — raw librosa beat tracks
- `windows/` — 19s track windows
- `clip_analysis/clips.json` — source clip profiles
- `Reel5_Phonk_v2.mp4` — sample render

## Status
8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole, shinigami, zora, addiction); 7 rendered. `clips/` must be re-downloaded before a fresh render.

> Note: beat detection (librosa) and the final render (ChatCut composite) are run via external tooling — only their data outputs (`beats/`, `plans/`, `windows/`, `clip_analysis/`) are committed here. `download_clips.sh` is the only committed script. See `CHANGELOG.md` for history.
