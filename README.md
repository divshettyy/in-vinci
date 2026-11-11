# reel-workdir — beat-synced phonk moto reel maker

Pipeline that turns slowed-phonk tracks + vertical moto source clips into
9:16 Instagram reels with cuts aligned to detected beats.

## Flow
1. **Beat detection** — librosa analyses each track; tempo + beat times saved to `beats/` and `plans/<slug>_beats.json` (also `beats_santafe.json` sample).
2. **Window cut** — ~19s hook window of each track exported to `windows/<slug>_19s.mp3`.
3. **Clip analysis** — source clips profiled in `clip_analysis/clips.json`.
4. **Cut plan** — `plans/<slug>.json`: beat-aligned `video_adds` (asset id, in-point, duration in frames, 9:16 crop/offset, audio muted to -60dB).
5. **Render** — plan + track window composited to the final reel.

## Source clips
Not committed (`clips/` is gitignored). Re-fetch from ChatCut:
```bash
echo 'PASTE_CHATCUT_COOKIE' > cookie.txt   # one line, never committed
bash download_clips.sh
```
17 asset UUIDs + project id live in `download_clips.sh`.

## Layout
- `plans/` — per-track cut plans + beat maps
- `beats/` — raw librosa beat tracks
- `windows/` — 19s track windows
- `clip_analysis/clips.json` — source clip profiles
- `Reel5_Phonk_v2.mp4` — sample render

## Status
8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole, shinigami, zora, addiction); 7 rendered. `clips/` must be re-downloaded before a fresh render.
