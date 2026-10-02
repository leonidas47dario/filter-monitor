# Filter Monitor

A real-time classifier that watches existing Wyze camera feeds, decides whether each aquarium filter is running, and alerts the owner when one is not.

## Status

**Phase 1A — connect & collect**, on the 40-gal tank (Cam v4, RTSP beta). See the [implementation plan](docs/implementation-plan.md).

- [docs/implementation-plan.md](docs/implementation-plan.md): phases, current step, exit criteria
- [docs/phase0-feed-access.md](docs/phase0-feed-access.md): RTSP status per camera model, camera-to-tank map
- [docs/filter-monitor-brd-v0.3.docx](docs/filter-monitor-brd-v0.3.docx): Business Requirements Document v0.3
- [docs/brd-review.md](docs/brd-review.md): gaps and open questions from reviewing v0.3

## Running it

It runs on any always-on machine **on the home network** (it has to reach the camera's local IP): a Windows/Mac PC with Docker Desktop, a Linux box, a NAS, or a Raspberry Pi.

First, in either setup: copy `.env.example` to `.env` and fill in the RTSP password. Wrap it in single quotes if it contains `#`, `$` or spaces. `.env` is gitignored and never goes into the Docker image.

### Option A — Docker (recommended)

Install Docker (Windows/Mac: [Docker Desktop](https://www.docker.com/products/docker-desktop/)). Then, from the repo folder:

| Step | Command |
| --- | --- |
| 1. Test the connection | `docker compose run --rm tools check` |
| 2. Set the flow region | `docker compose run --rm tools roi`, which saves a gridded snapshot; then `docker compose run --rm tools roi --rect x,y,w,h` |
| 3. Start collecting (runs in the background, restarts by itself) | `docker compose up -d --build` |
| Watch it / stop it | `docker compose logs -f collect` / `docker compose down` |
| 4. Staged outage (guided) | `docker compose run --rm tools staged --notes "day, lights on"` |

The first command builds the image, which takes a few minutes once. Set your time zone in `docker-compose.yml` (default `America/Chicago`). Docker Desktop must be set to start when you sign in, so the collector comes back after a reboot.

### Option B — plain Python

Install **Python 3.10+** and **ffmpeg** (Windows: `winget install Python.Python.3.12` and `winget install Gyan.FFmpeg`), then:
```
python -m venv .venv
.venv\Scripts\activate        (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```
The commands are the same, run as `python -m filter_monitor <command>`: `check`, `roi` (opens a window to drag the box), `collect`, `staged`. Add `--help` to any command for options.

### Output

Everything is written under `data/` (gitignored):

- `data/manifest.csv`: one row per clip, with label, stream status or error, resolution, fps, day/IR flag, motion in the ROI and the whole frame, and frozen-frame share
- `data/clips/<camera>/<date>/`: the recorded clips (.mkv, original quality, audio kept)
- `data/snapshots/`: frames with the ROI (or a coordinate grid) drawn on them

`collect` defaults to a 10 s clip about every 5 minutes, which is roughly 0.5–1 GB a day per camera at full resolution. Change it with `--interval` and `--duration` (with Docker, edit `command:` in `docker-compose.yml`).

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
