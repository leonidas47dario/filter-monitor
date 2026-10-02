# Filter Monitor

A real-time classifier that watches existing Wyze camera feeds, decides whether each aquarium filter is running, and alerts the owner when one is not.

## Status

Requirements stage. No code yet.

- [docs/filter-monitor-brd-v0.3.docx](docs/filter-monitor-brd-v0.3.docx) — Business Requirements Document, v0.3 draft (2026-10-01)
- [docs/brd-review.md](docs/brd-review.md) — gaps and open questions found reviewing v0.3

## Roadmap (from the BRD)

| Phase | Delivers |
| --- | --- |
| 0 — Audit | Per-tank inventory: camera model, filter type, flow visibility, feed access |
| 1 — MVP | One tank end to end: feed → classification → confirmed alert → review log |
| 2 — Rollout | All camera-monitored tanks, event history, dashboard, per-tank configuration |
| 3 — Candidates | Reduced-flow detection, quiet hours, audio, non-Wyze cameras |
