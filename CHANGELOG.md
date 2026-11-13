# Changelog

All notable changes to in-vinci (beat-synced phonk moto reel maker).

## [Unreleased]
### Added
- `LICENSE` (MIT) for code/pipeline data, with an explicit carve-out noting
  the committed sample audio/video is third-party/licensed and not covered.
- `.github/workflows/validate.yml` — lightweight CI stub that parses every
  `plans/*.json` and `beats/*.json` file and checks required keys are
  present, so a malformed plan/beat-map fails fast on push/PR.
- README rewritten for public/portfolio readability: pipeline diagram,
  features, tech stack, prerequisites, verified install/run steps, config,
  layout, media/copyright note, and roadmap.

### Fixed
- `download_clips.sh` now resolves `clips/` and `cookie.txt` relative to the
  script's own location instead of the hardcoded `~/reel-workdir/` path. After
  the repo was renamed from `reel-workdir` to `in-vinci`, the old paths made the
  script download into a non-existent directory; it now writes into the repo's
  own `clips/` regardless of checkout location.
- Removed the hardcoded local absolute path
  (`/home/hakuza/reel-workdir/windows/...`) that had leaked into the
  `"window"` field of 7 `plans/*.json` files (addiction, funkcriminal,
  funkpower, santafe, semcontrole, shinigami, zora) — now a repo-relative
  `windows/<slug>_19s.mp3` path, same value, no machine/username exposure.
- `.gitignore` hardened for public release: added `.env*`, `venv/`/`.venv/`,
  `__pycache__/`, `node_modules/`, `*.log`, and cache/temp-media patterns, on
  top of the existing `cookie.txt`/`clips/`/`out/` entries.

### Known gaps
- The beat-detection (librosa) and render (ChatCut composite) steps are run
  via external tooling and are not committed as scripts in this repo — only
  their data outputs (`beats/`, `plans/`, `windows/`, `clip_analysis/`) are.
- No automated tests beyond the new JSON-shape CI check; no error handling
  around network failures beyond `download_clips.sh`'s per-clip HTTP-code/size
  check; the ChatCut project id and 17 clip asset UUIDs are hardcoded in
  `download_clips.sh` rather than configurable.

## [0.1.0] — initial import
- Beat-synced phonk moto reel pipeline: librosa beat detection, 19s hook
  windows, source-clip profiling, beat-aligned 9:16 cut plans, final render.
- 8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
  shinigami, zora, addiction); 7 rendered.
- `download_clips.sh` helper to re-fetch the 17 source clips from ChatCut.
- Sample render committed as `Reel5_Phonk_v2.mp4`.
- Repo renamed from `reel-workdir` to `in-vinci`.
