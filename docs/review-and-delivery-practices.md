# Review and delivery practices

Ported on 2026-11-28 from a separate motorbike ride-to-Reels pipeline whose notes
(plan, runbook, lessons log) were shared by a friend. Only the parts that apply here are kept.
The friend's own audience preferences (no zoom, no grading, no text, no music-driven structure)
are that audience's taste, not this project's; they are exposed as opt-in flags, not defaults.

## What was adopted

| Practice | Where |
|---|---|
| Never repeat a source second across a set of reels | `reel_engine.py plan --claims claims.json` |
| Planned ending (held frame + 0.7 s video/audio fade) for non-looping reels | `--ending fade` (default stays `loop`) |
| Option to drop every zoom for audiences that dislike it | `--no-zoom` |
| Look at footage and drafts as timestamped contact sheets before signing off | `engine/contact_sheet.py` |
| Footage first, music second; critics catch flaws but do not rebuild | `engine/SKILL.md` "Review before you say done" |
| Ship a silent copy plus the exact in-app start time of the track window | same section |
| Check the render is newer than its plan before announcing it | same section |
| After delivery, ask which reel and moment worked, store it as taste memory | same section |

## What was not adopted

- Hindi/Kannada transcription, GoPro telemetry, Google Drive sync: not relevant to this repo's flow.
- Windows paths, Intel Quick Sync encode flags, the friend's `render_reel_fx.py` effects toolkit:
  not included in the shared files (notes only), and rendering here goes through ChatCut.
- Third-party skills (clipify, video-use, etc.): not installed; unreviewed code.

## Finding that motivated the contact-sheet step

A 1 s contact sheet of the committed sample `Reel5_Phonk_v2.mp4` shows near-black frames at about
1 s and 7 s. The quality gate passed them, so a visual check of every draft is worth keeping.
