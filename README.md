# Filter Monitor

A real-time classifier that watches existing Wyze camera feeds, decides whether each aquarium filter is running, and alerts the owner when one is not.

## Status

**Phase 1A — connect & collect**, on the 40-gal tank (Cam v4, RTSP beta). See the [implementation plan](docs/implementation-plan.md).

- [docs/implementation-plan.md](docs/implementation-plan.md): phases, current step, exit criteria
- [docs/phase0-feed-access.md](docs/phase0-feed-access.md): RTSP status per camera model, camera-to-tank map
- [docs/filter-monitor-brd-v0.3.docx](docs/filter-monitor-brd-v0.3.docx): Business Requirements Document v0.3
- [docs/brd-review.md](docs/brd-review.md): gaps and open questions from reviewing v0.3

## Setup (on a PC on the home network)

1. Install **Python 3.10+** and **ffmpeg**. On Windows: `winget install Python.Python.3.12` and `winget install Gyan.FFmpeg`, then open a new terminal.
2. From the repo folder:
   ```
   python -m venv .venv
   .venv\Scripts\activate        (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the RTSP password. Wrap it in single quotes if it contains `#`, `$` or spaces. `.env` is gitignored, so it never gets committed.

## Phase 1A commands

| Step | Command |
| --- | --- |
| 1. Test the connection | `python -m filter_monitor check` |
| 2. Draw the flow region | `python -m filter_monitor roi` |
| 3. Collect footage (leave running) | `python -m filter_monitor collect` |
| 4. Staged outage (guided) | `python -m filter_monitor staged --notes "day, lights on"` |

Add `--help` to any command for options. Everything is written under `data/` (gitignored):

- `data/manifest.csv`: one row per clip, with label, stream status or error, resolution, fps, day/IR flag, motion in the ROI and the whole frame, and frozen-frame share
- `data/clips/<camera>/<date>/`: the recorded clips (.mkv, original quality, audio kept)
- `data/snapshots/`: frames with the ROI drawn on them

`collect` defaults to a 10 s clip about every 5 minutes, which is roughly 0.5–1 GB a day per camera at full resolution. Change this with `--interval` and `--duration`.

## Roadmap

| Phase | Delivers |
| --- | --- |
| 0 — Audit | Feed access per camera (done for the 40-gal pilot) |
| 1A — Connect & collect | Reliable feed, labeled footage incl. staged outages ← **now** |
| 1B — Detector | Running/stopped decision from the ROI, scored on 1A footage |
| 1C — Alerting & ops | Confirmation window, push + backup alert, snooze, review log, heartbeat |
| 1D — Pilot | Two weeks live on one tank |
| 2 — Rollout | All camera-monitored tanks, event history, dashboard, per-tank configuration |
| 3 — Candidates | Reduced-flow detection, quiet hours, audio, non-Wyze cameras |
