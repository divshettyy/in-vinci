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

## [0.1.0] — initial import
- Beat-synced phonk moto reel pipeline: librosa beat detection, 19s hook
  windows, source-clip profiling, beat-aligned 9:16 cut plans, final render.
- 8 tracks planned (santafe, diabolica, funkcriminal, funkpower, semcontrole,
  shinigami, zora, addiction); 7 rendered.
- `download_clips.sh` helper to re-fetch the 17 source clips from ChatCut.
- Sample render committed as `Reel5_Phonk_v2.mp4`.
- Repo renamed from `reel-workdir` to `in-vinci`.
