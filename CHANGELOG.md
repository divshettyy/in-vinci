# Changelog

All notable changes to in-vinci (beat-synced phonk moto reel maker).

## [Unreleased]
### Added
- `tools/preview_timeline.py`: renders a self-contained HTML/SVG timeline of every plan (clips, beat grid, drop marker, per-cut beat offset coloured green/red) so beat-sync can be checked by eye without rendering. Tests added.
### Added
- `tools/snap_drop.py`: adds a non-destructive `drop_time_beat` (nearest grid beat) to every beat map, so downstream cutters target a beat that a hard cut can actually land on instead of the raw detector onset (up to 348 ms off). `--check` mode; tests added.
### Fixed
- `validate_plans.py --report` no longer cries "NO CUT ON THE DROP" for plans whose cut already sits on the beat nearest the drop (the drop rarely lands exactly on the grid). New `drop_beat_alignment_ms()` reports how far `drop_time` is off-grid and the cut-to-beat offset; real misses are still flagged. Finding: four plans have `drop_time` 116–348 ms off the beat grid, suggesting the drop detector (not the cuts) needs tightening. 2 new tests.
### Added
- `tools/align_drop.py`: moves the cut nearest the beat drop onto the beat nearest the drop (trading frames between the two neighbouring clips; total length and all other cuts unchanged; never creates a flicker clip). Applied to `funkcriminal` (drop offset 539 ms -> 27 ms) and `semcontrole` (478 ms -> 155 ms). `--check` mode for CI; tests added.
### Added
- `validate_plans.py --report` now prints `drop_alignment_ms()`: signed offset from the beat map's `drop_time` to the nearest cut, flagging plans with no cut on the drop (currently 5 of 8). Report-only; 3 new tests.
- `validate_plans.py --report` now prints cut pacing per plan (mean/min/max clip length, accelerating-into-drop flag, monotone-rhythm flag) via new `pacing()`; 3 new tests.

### Fixed
- Cut timing: per-clip frame rounding accumulated up to ~3 frames (~100 ms) of drift by the end of each reel, so late cuts missed the beat. All 8 plans re-timed from their beat-aligned `boundaries_s` (`tools/retime_plans.py`); total lengths unchanged.
### Added
- `tools/validate_plans.py --report`: per-plan mean/max cut-to-beat offset in ms (signed offsets via `cut_offsets_ms`), with tests. Current plans: mean 7–10 ms, max ≤ 17 ms.
- `tools/validate_plans.py` beat-sync validator, unit tests, CI step.
### Added
- `LICENSE` (MIT) for code/pipeline data, with an explicit carve-out noting
  the committed sample audio/video is third-party/licensed and not covered.
- `.github/workflows/validate.yml` — lightweight CI stub that parses every
  `plans/*.json` and `beats/*.json` file and checks required keys are
  present, so a malformed plan/beat-map fails fast on push/PR.
- README rewritten for public/portfolio readability: pipeline diagram,
  features, tech stack, prerequisites, verified install/run steps, config,
  layout, media/copyright note, and roadmap. Also documents the actual
  runtime deps (bash/curl, ffmpeg, Python + librosa, opencv-python +
  scenedetect) and clarifies that `download_clips.sh` reads the cookie from
  `cookie.txt` at runtime rather than ever hardcoding it, and that no other
  secrets/env vars are required.

### Security
- Audited for hardcoded secrets/API keys, unsafe shell quoting, `eval` use,
  and command injection — none found. `download_clips.sh` has no user-supplied
  filenames/URLs reaching the shell (the clip name -> UUID map is hardcoded)
  and all variable expansions are quoted. Also audited full git history
  (`git log -p`) for leaked credentials/cookies/tokens — none found, only
  placeholder text (`PASTE_CHATCUT_COOKIE`).
- `download_clips.sh`: removed a redundant/stale `-b "chatcut=dummy"` curl
  flag that was sent alongside the real `-H "cookie: ..."` header — harmless
  but confusing, and risked a duplicate/malformed `Cookie` header.
- `.gitignore` hardened for public release: added `.env`/`.env.*`
  (`!.env.example` kept trackable), `venv/`/`.venv/`, `__pycache__/`/`*.pyc`,
  `.ipynb_checkpoints/`, `node_modules/`, `*.log`/cache patterns, and
  `.DS_Store`/`*.swp` editor noise, on top of the existing
  `cookie.txt`/`clips/`/`out/` entries.

### Fixed
- `download_clips.sh` now resolves `clips/` and `cookie.txt` relative to the
  script's own location instead of the hardcoded `~/reel-workdir/` path. After
  the repo was renamed from `reel-workdir` to `in-vinci`, the old paths made the
  script download into a non-existent directory; it now writes into the repo's
  own `clips/` regardless of checkout location.
- **Stale `window` path in `plans/*.json`**: the same `reel-workdir` rename left
  every rendered plan's `window` field pointing at the now-nonexistent
  `/home/hakuza/reel-workdir/windows/<slug>_19s.mp3` — a leaked local absolute
  path (machine/username exposure) as well as a broken reference. Any
  render/composite tool that reads a plan and opens `window` to pull in the
  track's audio hook would fail to find the file on a fresh checkout. Rewrote
  all 7 (`addiction`, `funkcriminal`, `funkpower`, `santafe`, `semcontrole`,
  `shinigami`, `zora`) to the repo-relative `windows/<slug>_19s.mp3`, which is
  exactly where the file already lives — verified present for each before
  rewriting, and every plan file still parses as valid JSON after the change.
  `diabolica.json` (the one planned-but-not-rendered track) has no
  `window`/`track_file` fields at all — left untouched, since there's no
  evidence of what it should contain.

### Known gaps
- The beat-detection (librosa) and render (ChatCut composite) steps are run
  via external tooling and are not committed as scripts in this repo — only
  their data outputs (`beats/`, `plans/`, `windows/`, `clip_analysis/`) are.
- No automated tests beyond the new JSON-shape CI check; no error handling
  around network failures beyond `download_clips.sh`'s per-clip HTTP-code/size
  check; the ChatCut project id and 17 clip asset UUIDs are hardcoded in
  `download_clips.sh` rather than configurable.

## [2026-11-20] — discoverability and tooling pass (no code behaviour change)
### Added
- Dependabot configuration for weekly grouped GitHub Actions updates (the pipeline
  is stdlib-only, so there is no Python manifest for Dependabot to track).
- `.editorconfig` so every contributor shares the same indentation and line endings.
### Notes
- The 23 MB `Reel5_Phonk_v2.mp4` sample and the 384 KB `track_santafe_19s.mp3` are
  committed to the repository. They inflate every clone; consider moving them to a
  release asset or Git LFS. Removing them from history is a rewrite, so it was left
  for a deliberate decision rather than done automatically here.

## [0.1.0] — initial import
- Beat-synced phonk moto reel pipeline: librosa beat detection, 19s hook
  windows, source-clip profiling, beat-aligned 9:16 cut plans, final render.
- 8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
  shinigami, zora, addiction); 7 rendered.
- `download_clips.sh` helper to re-fetch the 17 source clips from ChatCut.
- Sample render committed as `Reel5_Phonk_v2.mp4`.
- Repo renamed from `reel-workdir` to `in-vinci`.

## 2026-11-20 — Media purged from history

Removed all audio and video binaries from the entire git history with
`git-filter-repo` (23 MB `Reel5_Phonk_v2.mp4` plus nine `*_19s.mp3` phonk-track
windows). These were sample artifacts combining third-party copyrighted slowed-
phonk tracks with rendered output — they bloated every clone to ~26 MB and were
not safe to ship in a public repo. The pack is now ~280 KB. Added `*.mp4`,
`*.mp3`, `*.mov`, `*.wav`, and `windows/` to `.gitignore`, and rewrote the
README "Media & copyright" section to state that no third-party media is
committed and must be supplied locally. Pipeline code and tests are unaffected
(they read `plans/*.json`, never the media binaries).
