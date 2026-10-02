# BRD v0.3 review — gaps and open questions

Review of [filter-monitor-brd-v0.3.docx](filter-monitor-brd-v0.3.docx), 2026-10-01.

Scope and alert policy are well defined. The success metrics can't be measured as written, and a few feasibility items are deferred that could sink the approach.

## Gaps that change the design

1. **Recall (SC-2) can't be measured from the review log.** The log only holds alerts that fired, so a missed stoppage never appears in it. Real stoppages are also rare; a two-week single-tank MVP may see none. Recall needs a staged-outage protocol, and showing ≥95% with confidence takes about 59 consecutive catches, not a handful.
2. **SC-3 and SC-4 contradict each other.** At 3 false alerts per tank per month, 80% precision would require about 12 real stoppages per tank per month. One of these targets has to go, and SC-4 is the meaningful one.
3. **No household false-alert number, and no tank count.** At 10 tanks, SC-4 allows roughly one false alert a day, delivered as a loud push with no quiet hours.
4. **Camera loss is treated as "never a filter alert" (FR-1).** If a camera and filter share a power strip or GFCI, a tripped circuit kills both, and the most likely real failure is reported as a low-urgency stream fault. Stream-fault alerts have no defined latency, channel or severity.
5. **Power restore isn't covered.** Filters often fail to restart or re-prime after an outage. NFR-2 covers restart after a crash but not after a reboot, and nothing requires a prompt re-check of every tank once feeds return.
6. **Frozen or stale frames aren't addressed.** A stuck stream showing an old "running" frame is a silent miss, which is the worst outcome under recall-first tuning.
7. **Phase 0 has no go/no-go.** The only fallback for no feed access is "reposition or replace the camera", but non-Wyze cameras are out of scope and replacements break the $0 target. Official RTSP is believed to exist only on a few older Wyze models, with the alternatives relying on unofficial APIs — unverified, to confirm in Phase 0.
8. **The "flow visible" audit asks the wrong question.** What matters is whether stopped is distinguishable from running, especially with airstones or wavemakers in the tank. Only the staged outage shows that, so it belongs in Phase 0, not just scheduled there.

## Inconsistencies and smaller holes

- **Latency clock:** SC-1 and NFR-1 don't say whether the 10 minutes includes the 5-minute confirmation window.
- **Cooldown vs. recall-first:** a second real stop inside the 60-minute cooldown is suppressed. It's also unclear whether the cooldown blocks escalation re-sends, or whether a still-stopped filter ever re-alerts after acknowledgement.
- **Acknowledgement:** escalation depends on it, but there is no mechanism for it and no native app.
- **Snapshot:** a still image can't show flow; a short clip would be needed to judge an alert remotely.
- **Held-out tanks (Section 8):** impossible in a single-tank MVP. It also sits oddly with NFR-5 if each new tank needs its own staged outage and calibration.
- **FR-12 in Phase 1:** whole-home detection is untestable on one tank, where one feed lost equals all feeds lost.
- **Away mode:** a "Should" in Phase 2, yet described as the costliest failure case.
- **Unowned requirements:** the daily/weekly digest, the camera-fault alert type and per-mode thresholds appear only in the policy and risk sections, with no FR, priority or phase.
- **Privacy (NFR-3):** forbids cloud upload without approval but also accepts cloud inference. Snapshot-only retention also conflicts with collecting training clips.
- **$0 target:** SMS backup and a push that breaks through Do Not Disturb typically cost money or need platform-specific entitlements.
- **Remote access:** nothing says how the dashboard and snooze are reached while travelling, or how that access is secured.
- **Not covered at all:** ROI drift from a bumped or panning camera, algae or condensation, water-level changes, a maximum snooze duration, and a way to report a miss.

## Questions for the owner

1. How many tanks, and which camera models and firmware?
2. What is the "existing home hardware", and is it always on?
3. iPhone or Android? This decides whether a loud push that breaks through Do Not Disturb is feasible for free.
4. How long from a filter stop to actual harm in the most sensitive tank? If it's hours, a 30–60 minute confirmation window would cut false alerts sharply at no cost to recall.
5. What caused the past failures (dead motor, lost prime after a power blip, unplugged, air pump)?
6. Are cameras and filters on the same power strip or circuit?
7. When travelling, who can physically act on an alert?
8. Is periodic sampling (say, a 10-second clip each minute) acceptable instead of a continuous stream? That widens the feed-access options.
9. Does any tank have more than one filter, or other flow sources in frame? Does any camera cover more than one tank?
10. What household-wide false-alert rate is tolerable, particularly overnight?
