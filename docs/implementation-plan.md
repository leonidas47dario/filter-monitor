# Implementation plan

Drafted 2026-10-02 · Builds on [BRD v0.3](filter-monitor-brd-v0.3.docx), [the review](brd-review.md) and [Phase 0 findings](phase0-feed-access.md).

## Why phases, and what changed

The BRD's Phase 1 bundles feed, classifier, alerts, snooze, outage detection and a two-week pilot into one step. That's too much to commit to before we know what the camera footage looks like. The detector design depends on the data: whether a stopped filter is visibly different from a running one in the region of interest (ROI), by day and under infrared at night. So Phase 1 is split, and **Phase 1A (connect and collect) is the only thing in flight now**. Nothing in 1B or later gets built until 1A's exit criteria are met.

Phase 0 is done for the pilot tank: the 40-gallon tank's Cam v4 has RTSP enabled and is in `config/cameras.yaml`. The other tanks' Phase 0 items (Pan v4 and Window Camera bridge, v3 Pro toggle) stay open and move into Phase 2.

| Phase | Delivers | Status |
| --- | --- | --- |
| 0 — Audit | Feed-access path per camera | Done for 40-gal pilot; other tanks deferred to Phase 2 |
| **1A — Connect & collect** | Reliable feed on the pilot tank, labeled footage including staged outages | **In progress** |
| 1B — Detector | Running/stopped decision from the ROI, measured against the 1A footage | Next |
| 1C — Alerting & ops | Confirmation window, push + backup alert, snooze, review log, outage heartbeat | After 1B |
| 1D — Pilot | Two weeks live on the 40-gal tank (BRD Phase 1 exit criteria) | After 1C |
| 2 — Rollout | Remaining tanks (bridge for Pan v4 / Window Camera), dashboard, history, away mode | — |
| 3 — Candidates | Reduced flow, quiet hours, audio, non-Wyze cameras | — |

## Phase 1A — Connect & collect (now)

Goal: prove the feed is dependable and collect the footage the detector will be built and graded on. No model, no alerts.

**Tools (in this repo, run on a PC on the home network):**

| Command | What it does |
| --- | --- |
| `python -m filter_monitor check` | Connection test: network reachability, stream opens, resolution/fps, frozen-frame check, saves a snapshot |
| `python -m filter_monitor roi` | Draw the flow region on a fresh frame; saved to `config/rois.yaml` |
| `python -m filter_monitor collect` | Unattended sampler: a short clip every few minutes, logged to a manifest with a motion score, day/night flag and stream errors |
| `python -m filter_monitor staged` | Guided staged outage: records running → stopped → restarting clips, each labeled |

Footage stays in `data/` (gitignored), never in the repo or any cloud.

**Steps:**

1. Run `check` until it passes. *(Owner, ~10 min)*
2. Draw the ROI over the filter outflow with `roi`, then re-run `check` to confirm the frame. *(Owner, ~5 min)*
3. Leave `collect` running for 72 hours, covering at least 2 nights of IR mode. *(Unattended)*
4. Run 3 staged outages by day and 2 at night: each one is a 2-minute unplug, guided by `staged`. *(Owner, ~10 min each)*
5. Review the manifest together: stream uptime, errors, and whether the ROI motion score separates running from stopped. *(Owner + Claude)*

**Exit criteria (go/no-go for 1B):**

- Stream uptime ≥ 99% of collection attempts over 72 h; every drop recovers on its own (FR-1 evidence).
- No frozen-frame samples, or each one explained.
- ≥ 5 labeled stopped clips (day and night) and ≥ 2 days of running samples.
- Visible separation in ROI motion score between running and stopped, day and night. If there is no separation, move the ROI or the camera before 1B. This is the review's gap 8 ("is stopped distinguishable?"), answered with data.

**Decisions to settle during 1A:** the stream resolution to keep (`/stream0` vs a lower substream) and the disk budget. At 10 s every 5 min, expect roughly 0.5–1 GB a day per camera.

## Phase 1B — Detector

- Baseline first: frame-difference motion energy in the ROI, with separate day and IR thresholds (R-1). This is the BRD's "established signal-processing trick".
- Score it on the 1A clips. Recall on staged stops is the gate (SC-2); false positives on running samples come second.
- Only if the baseline fails: try a pretrained vision backbone with a small classifier head on ROI crops (BRD Section 8: no models built from scratch).
- Add a stale-stream guard: identical consecutive frames mean a stream fault, never "running" (review gap 6).

## Phase 1C — Alerting & ops

- State machine: stopped for 5 minutes continuously → alert; 60-minute cooldown; escalation if unacknowledged (FR-4, FR-5).
- Free channels first (NFR-4): ntfy push (loud, priority 5) as primary; email as backup.
- Maintenance snooze (FR-11) and a review log with correct/incorrect labels (FR-6).
- External heartbeat on a free tier, e.g. healthchecks.io. If the monitor goes silent, the owner still gets paged (FR-12, SC-6).
- Auto-start and auto-restart on the home PC (NFR-2).

## Phase 1D — Pilot

This is the BRD's Phase 1 acceptance: two weeks live on the 40-gal tank, every alert labeled, plus staged outages to measure recall. Staged outages are needed because the review log alone can't show missed stops (review gap 1).

## Open items for the owner

- Which PC will run the monitor around the clock, and is it Windows? (Phase 1C auto-start depends on it.)
- iPhone or Android? (Decides how a loud push can break through Do Not Disturb.)
- Are the camera and filter on the same power strip? (Review gap 4.)
