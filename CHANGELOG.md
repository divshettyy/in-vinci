# Changelog

All notable changes to in-vinci (beat-synced phonk moto reel maker).

## [Unreleased]
### Fixed
- `download_clips.sh` now resolves `clips/` and `cookie.txt` relative to the
  script's own location instead of the hardcoded `~/reel-workdir/` path. After
  the repo was renamed from `reel-workdir` to `in-vinci`, the old paths made the
  script download into a non-existent directory; it now writes into the repo's
  own `clips/` regardless of checkout location.
- **Stale `window` path in `plans/*.json`**: the same `reel-workdir` rename left
  every rendered plan's `window` field pointing at the now-nonexistent
  `/home/hakuza/reel-workdir/windows/<slug>_19s.mp3`. Any render/composite tool
  that reads a plan and opens `window` to pull in the track's audio hook would
  fail to find the file on a fresh checkout. Rewrote all 7 (`addiction`,
  `funkcriminal`, `funkpower`, `santafe`, `semcontrole`, `shinigami`, `zora`) to
  the repo-relative `windows/<slug>_19s.mp3`, which is exactly where the file
  already lives — verified present for each before rewriting, and every plan
  file still parses as valid JSON after the change. `diabolica.json` (the one
  planned-but-not-rendered track) has no `window`/`track_file` fields at all —
  left untouched, since there's no evidence of what it should contain.

### Known gaps
- The beat-detection (librosa) and render (ChatCut composite) steps are run
  via external tooling and are not committed as scripts in this repo — only
  their data outputs (`beats/`, `plans/`, `windows/`, `clip_analysis/`) are.

## [0.1.0] — initial import
- Beat-synced phonk moto reel pipeline: librosa beat detection, 19s hook
  windows, source-clip profiling, beat-aligned 9:16 cut plans, final render.
- 8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
  shinigami, zora, addiction); 7 rendered.
- `download_clips.sh` helper to re-fetch the 17 source clips from ChatCut.
- Sample render committed as `Reel5_Phonk_v2.mp4`.
- Repo renamed from `reel-workdir` to `in-vinci`.
