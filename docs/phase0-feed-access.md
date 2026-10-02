# Phase 0 — Feed access findings

Research date: 2026-10-01 · Owner: Jarvis (PM) · Status: findings complete; owner actions pending

## Wyze RTSP landscape

Wyze's official in-app RTSP program is real: on a supported camera,
Device → Settings → Advanced Settings → RTSP → Set Up → create a
username/password → Generate URL. The app shows `rtsp://…` (or `rtsps://…`).
Beta models need beta firmware (and the WyzeBeta app) before the toggle appears.

Sources: Wyze RTSP beta instructions (`wyze-beta.s3.us-west-2.amazonaws.com/rtsp.html`);
Wyze forum, Sep 2026 ("v3 and Panv3 have had both RTSP and RTSPS in production
firmware for months now. v4 has it in Beta").

| Camera | RTSP status (as of Oct 2026) |
|---|---|
| Cam v3, Cam Pan v3 | Production firmware (RTSP + RTSPS) |
| Cam v4 | **Beta** — in-app toggle after beta firmware update |
| Cam v3 Pro | In an early beta test (Jan 2026); unconfirmed — check the camera's Advanced Settings |
| Cam Pan v4, Window Camera | No RTSP path; nothing announced |

Beta caveats: Wyze ships it "for initial testing only" and won't commit to
fixing issues before the official build. The RTSP password is shown once —
keep stream URLs out of chat and out of this repo (local gitignored file only).

## Camera → tank map (owner-confirmed 2026-10-01)

| Tank | Camera | Feed-access plan |
|---|---|---|
| 75-gal | Cam Pan v4 (4K) | No native RTSP → bridge |
| 75-gal | Wyze Window Camera | No native RTSP → bridge; may cover the sponge filter |
| 20-gal | Cam v3 Pro (2K) | Check for beta RTSP toggle; else bridge |
| 40-gal | Cam v4 (2.5K) | In-app RTSP beta — primary path |

Unassigned: 2019 Cam Pan v1, Cam v2 (possibly retired — owner to confirm).

## Fallback: docker-wyze-bridge

Free, runs in Docker (or WSL on Windows). Converts the Wyze stream to RTSP for
all models, so it covers the Pan v4 and Window Camera. Note: on the v4 the
bridge path may be limited to 640×360 — likely fine for flow detection in an
ROI, to be validated in the spike. Alternative: TinyCam Pro in server mode
(paid, Android).

## Owner actions

- [ ] Enroll in Wyze beta, update the Cam v4 (40-gal) to beta firmware, enable RTSP, generate the URL
- [ ] Check the Cam v3 Pro (20-gal) Advanced Settings for the RTSP toggle
- [ ] Confirm whether the 2019 cameras are still deployed anywhere
- [ ] Stream URLs go in a local gitignored file only — never chat, never the repo
