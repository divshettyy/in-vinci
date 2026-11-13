# in-vinci — beat-synced phonk moto reel maker

Turns slowed-phonk tracks + vertical moto footage into 9:16 Instagram reels,
with every cut landing on a detected beat.

> Demo: _add a link or embed here once a reel is published (e.g. Instagram
> permalink or a GIF preview of `Reel5_Phonk_v2.mp4`)._

## Pipeline

```
track.mp3 ──▶ beat detection (librosa) ──▶ beats/*.json (tempo + beat times)
                                              │
                                              ▼
                                  19s hook window ──▶ windows/*_19s.mp3
                                              │
source clips ──▶ clip profiling ──▶ clip_analysis/clips.json
      (shot splits, rotation, slow-mo flags)  │
                                              ▼
                              beat-aligned cut plan ──▶ plans/<slug>.json
                                              │
                                              ▼
                        render (ChatCut composite) ──▶ final 9:16 .mp4
```

1. **Beat detection** — `librosa` analyses each track; tempo + beat
   timestamps are saved to `beats/` (raw) and `plans/<slug>_beats.json`
   (per-track; see also the `beats_santafe.json` sample at repo root).
2. **Window cut** — a ~19s hook window of each track is exported to
   `windows/<slug>_19s.mp3`.
3. **Clip analysis** — source moto clips are profiled (duration, fps,
   rotation, shot boundaries, slow-mo detection) into
   `clip_analysis/clips.json`.
4. **Cut plan** — `plans/<slug>.json` describes the edit as a list of
   `video_adds`: source asset id, in-point (`sourceStartFromInSeconds`),
   clip duration in frames, 9:16 crop/offset (`width`/`height`/`left`/`top`),
   and the clip's own audio muted to `-60dB` so only the track plays.
5. **Render** — the cut plan + track window are composited into the final
   vertical reel (`Reel5_Phonk_v2.mp4` is a sample output).

**What's actually in this repo:** the beat-detection and render steps run via
external tooling (a local `librosa` script and a ChatCut composite job) that
are *not* committed here — only their data outputs (`beats/`, `plans/`,
`windows/`, `clip_analysis/`) are. The one committed, runnable script is
`download_clips.sh`, which re-fetches the source clips referenced by the cut
plans.

## Features

- Automatic tempo + beat-grid extraction from any phonk/slowed track
- Beat-aligned cut timing — no manual scrubbing to find the drop
- Per-clip shot-boundary and slow-motion detection to avoid cutting mid-shot
- 9:16 crop/offset baked into each plan for Instagram Reels / TikTok framing
- Clip audio auto-muted so only the soundtrack plays
- 8 tracks planned, 7 rendered, reusable against a 17-clip moto footage pool

## Tech stack

- **Beat detection:** Python + [`librosa`](https://librosa.org/) (external,
  not committed — see note above)
- **Clip analysis:** Python + OpenCV / `scenedetect` (external; outputs
  committed as `clip_analysis/clips.json`)
- **Render / composite:** [ChatCut](https://chatcut.io) API
- **Source fetch:** `bash` + `curl` (`download_clips.sh`)
- **Media:** `ffmpeg` (implied by any local re-render of the window/clip
  audio-video; not directly invoked by committed scripts)

## Prerequisites

- `bash`, `curl`
- A ChatCut account with access to the source project (for `download_clips.sh`
  and for re-rendering plans)
- For re-running beat detection / clip analysis yourself (scripts not
  included): Python 3, `librosa`, `opencv-python`, `scenedetect`, `ffmpeg`

## Install & run

Clone, then re-fetch the source clips (not committed — see
[Media & copyright](#media--copyright)):

```bash
git clone https://github.com/divshettyy/in-vinci.git
cd in-vinci

# one-time: get your ChatCut session cookie
#   DevTools (F12) -> Network -> any request to api.chatcut.io
#   -> Request Headers -> copy the whole `cookie:` value
echo 'PASTE_CHATCUT_COOKIE' > cookie.txt   # one line, gitignored, never committed

bash download_clips.sh   # pulls the 17 source clips into clips/
```

`download_clips.sh` resolves `clips/` and `cookie.txt` relative to its own
location, so it works from any checkout path. It prints `ok`/`FAIL` per clip;
a `FAIL` usually means the cookie expired — re-copy it and re-run.

Beat detection, clip analysis, and the final render are run externally
against this data (see the pipeline diagram above); the JSON outputs in
`beats/`, `plans/`, `windows/`, and `clip_analysis/` are what those external
steps produced and are checked in so a plan can be inspected or re-rendered
without re-running analysis from scratch.

## Config

- `download_clips.sh` hardcodes the ChatCut project id and the 17
  `name -> asset UUID` pairs for the source clip pool. Swap these to point at
  a different ChatCut project/clip set.
- Each `plans/<slug>.json` is self-contained: track filename, detected
  `tempo`/`phase`, cut count, and the full `video_adds` list. Edit a plan
  directly to tweak crop offsets or swap a clip's asset id.

No secrets or environment variables are required beyond the gitignored
`cookie.txt` consumed by `download_clips.sh` (see Install & run above).

## Layout

```
beats/                  raw librosa beat tracks (tempo + beat timestamps)
plans/                  per-track cut plans (<slug>.json) + beat maps (<slug>_beats.json)
windows/                19s hook-window renders of each track
clip_analysis/clips.json  source clip profiles (shots, rotation, slow-mo)
clips/                  source moto clips (gitignored — re-fetch with download_clips.sh)
out/                    scratch render output (gitignored)
download_clips.sh       fetches the 17 source clips from ChatCut
beats_santafe.json      standalone sample beat map
track_santafe_19s.mp3   standalone sample track window
Reel5_Phonk_v2.mp4      sample rendered reel
```

## Status

8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
shinigami, zora, addiction); 7 rendered. `clips/` must be re-downloaded
before a fresh render. See `CHANGELOG.md` for history.

## Media & copyright

The committed audio samples (`track_santafe_19s.mp3`, `windows/*.mp3`) are
short (~19s) excerpts of third-party slowed-phonk tracks, used here only to
demonstrate the beat-detection/cut-plan pipeline. The sample render
(`Reel5_Phonk_v2.mp4`) likewise combines a licensed/third-party track with
footage from the source clip pool. **These are not released under the MIT
license below** and should not be redistributed as standalone media — treat
them as pipeline-demo artifacts, not licensed assets. The source moto clips
themselves are not committed at all (`clips/` is gitignored) and must be
supplied by whoever owns/has rights to that footage.

## Roadmap

- [ ] Commit the beat-detection and clip-analysis scripts themselves (not
      just their outputs) so the pipeline is fully reproducible from this repo
- [ ] Swap the ChatCut-cookie flow in `download_clips.sh` for a proper API
      token / OAuth flow
- [ ] Add a minimal test/CI stub (plan-schema validation, beat-map sanity
      checks)
- [ ] Parameterize `download_clips.sh`'s project id / asset list instead of
      hardcoding them

## License

Code and pipeline data: [MIT](LICENSE). Committed sample media is excluded —
see [Media & copyright](#media--copyright) above.
