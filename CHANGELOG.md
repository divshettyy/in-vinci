# Changelog

All notable changes to in-vinci (beat-synced phonk moto reel maker).

## [Unreleased]
### Fixed
- `download_clips.sh` now resolves `clips/` and `cookie.txt` relative to the
  script's own location instead of the hardcoded `~/reel-workdir/` path. After
  the repo was renamed from `reel-workdir` to `in-vinci`, the old paths made the
  script download into a non-existent directory; it now writes into the repo's
  own `clips/` regardless of checkout location.

### Known gaps
- The beat-detection (librosa) and render (ChatCut composite) steps are run
  via external tooling and are not committed as scripts in this repo — only
  their data outputs (`beats/`, `plans/`, `windows/`, `clip_analysis/`) are.
- The `window` field in `plans/*.json` still records the old absolute
  `/home/hakuza/reel-workdir/windows/...` path (historical render metadata).

## [0.1.0] — initial import
- Beat-synced phonk moto reel pipeline: librosa beat detection, 19s hook
  windows, source-clip profiling, beat-aligned 9:16 cut plans, final render.
- 8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
  shinigami, zora, addiction); 7 rendered.
- `download_clips.sh` helper to re-fetch the 17 source clips from ChatCut.
- Sample render committed as `Reel5_Phonk_v2.mp4`.
- Repo renamed from `reel-workdir` to `in-vinci`.
