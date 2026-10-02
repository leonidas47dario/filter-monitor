"""Phase 1A command line: check, roi, collect, staged.

Run from the repo root:  python -m filter_monitor <command> --help
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from . import config
from .config import Camera, ConfigError, DATA_DIR
from .stream import analyze_clip, draw_grid, draw_roi, ffmpeg_path, record_clip, tcp_reachable

MANIFEST = DATA_DIR / "manifest.csv"
MANIFEST_FIELDS = [
    "timestamp", "camera", "tank", "session", "label", "status", "file",
    "frames", "width", "height", "fps", "brightness", "ir_mode",
    "motion_frame", "motion_roi", "dup_frac", "error", "notes",
]


def say(tag: str, msg: str) -> None:
    print(f"  [{tag:<4}] {msg}", flush=True)


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(config.REPO_ROOT))
    except ValueError:
        return str(path)


def write_manifest(row: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def save_snapshot(cam: Camera, frame, tag: str) -> Path:
    path = DATA_DIR / "snapshots" / f"{cam.name}_{tag}_{stamp()}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), draw_roi(frame, cam.roi))
    return path


def capture(cam: Camera, duration: float, session: str, label: str, notes: str = "",
            audio: bool = True, folder: str = "clips") -> dict:
    """Record one clip, analyze it, log it to the manifest. Returns the manifest row."""
    now = datetime.now()
    out = DATA_DIR / folder / cam.name / now.strftime("%Y-%m-%d") / (
        f"{cam.name}_{now.strftime('%Y%m%d-%H%M%S')}_{label or 'unlabeled'}.mkv")
    row = {"timestamp": now.isoformat(timespec="seconds"), "camera": cam.name, "tank": cam.tank,
           "session": session, "label": label, "notes": notes}

    res = record_clip(cam, out, duration, audio=audio)
    if not res.ok:
        row.update(status="error", error=res.error)
        write_manifest(row)
        return row

    row["file"] = rel(out)
    try:
        st = analyze_clip(out, cam.roi)
    except RuntimeError as e:
        row.update(status="error", error=str(e))
        write_manifest(row)
        return row

    row.update(status="frozen" if st.frozen else "ok", frames=st.frames, width=st.width,
               height=st.height, fps=st.fps, brightness=st.brightness, ir_mode=int(st.ir_mode),
               motion_frame=st.motion_frame, motion_roi="" if st.motion_roi is None else st.motion_roi,
               dup_frac=st.dup_frac)
    row["_stats"] = st
    write_manifest(row)
    return row


# ---------------------------------------------------------------- check

def cmd_check(args) -> int:
    cams = config.load_cameras(args.camera)
    ffmpeg_path()
    failures = 0
    for cam in cams:
        print(f"\n{cam.name}  ({cam.model}, {cam.tank} tank)")
        try:
            cam.password  # noqa: B018 — raises a clear error if .env is missing it
            say("OK", f"password found in {cam.password_env}")
        except ConfigError as e:
            say("FAIL", str(e))
            failures += 1
            continue

        ok, msg = tcp_reachable(cam)
        say("OK" if ok else "FAIL", msg)
        if not ok:
            say("HINT", "Is this PC on the home network? Did the camera's IP change? Check it in "
                        "the Wyze app (Device Info) and consider a DHCP reservation on the router.")
            failures += 1
            continue

        t0 = time.monotonic()
        row = capture(cam, args.seconds, session="check", label="check", folder="check")
        if row["status"] == "error":
            say("FAIL", f"stream did not open: {row['error']}")
            say("HINT", "401/Unauthorized → wrong RTSP username or password (regenerate in the "
                        "Wyze app). TLS/handshake errors → confirm protocol and port in "
                        "config/cameras.yaml match the URL the app generated.")
            failures += 1
            continue
        st = row["_stats"]
        say("OK", f"stream opened and recorded {args.seconds:g}s in {time.monotonic() - t0:.1f}s "
                  f"→ {row['file']}")
        say("OK", f"{st.width}x{st.height} @ {st.fps:g} fps, {st.frames} frames")
        if st.frozen:
            say("FAIL", "every frame is identical — the stream looks frozen")
            failures += 1
        else:
            say("OK", f"frames are live ({st.dup_frac:.0%} duplicate frame pairs)")
        say("INFO", f"{'IR night mode (black and white)' if st.ir_mode else 'colour/day mode'}, "
                    f"brightness {st.brightness:g}/255")
        if cam.roi:
            say("INFO", f"motion: ROI {st.motion_roi:g}, whole frame {st.motion_frame:g}")
        else:
            say("INFO", f"motion (whole frame) {st.motion_frame:g}; no ROI yet — "
                        "run the `roi` command next")
        if st.middle_frame is not None:
            say("OK", f"snapshot saved → {rel(save_snapshot(cam, st.middle_frame, 'check'))}")

    print("\nRESULT:", "all cameras passed" if failures == 0 else f"{failures} problem(s) found")
    return 0 if failures == 0 else 1


# ---------------------------------------------------------------- roi

def parse_rect(text: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4 or not all(0 <= p <= 1 for p in parts) or parts[2] <= 0 or parts[3] <= 0:
        raise argparse.ArgumentTypeError("expected x,y,w,h as fractions between 0 and 1")
    return tuple(parts)


def has_gui() -> bool:
    return "GUI: NONE" not in " ".join(cv2.getBuildInformation().split())


def draw_roi_window(cam: Camera, frame) -> tuple[float, float, float, float] | tuple | None:
    """Let the owner drag a box. Returns the ROI, () if cancelled, None if no window could open."""
    print("A window will open: drag a box tightly over where the filter's flow is visible "
          "(outflow lip, surface ripple, bubbles or spray bar). Press ENTER to save, C to cancel.")
    try:
        x, y, bw, bh = cv2.selectROI(f"Draw ROI - {cam.name}", frame, showCrosshair=True)
        cv2.destroyAllWindows()
    except cv2.error:
        return None  # GUI build but no display (e.g. a headless Linux box)
    if bw == 0 or bh == 0:
        return ()
    h, w = frame.shape[:2]
    return (x / w, y / h, bw / w, bh / h)


def cmd_roi(args) -> int:
    cams = config.load_cameras([args.camera] if args.camera else None)
    if len(cams) > 1:
        sys.exit(f"Several cameras configured — pick one with --camera ({', '.join(c.name for c in cams)})")
    cam = cams[0]

    print(f"Grabbing a frame from {cam.name}…")
    row = capture(cam, 3, session="roi", label="roi", folder="check", audio=False)
    if row["status"] == "error":
        sys.exit(f"Could not read the stream: {row['error']}\nRun the `check` command first.")
    frame = row["_stats"].middle_frame
    h, w = frame.shape[:2]

    if args.rect:
        roi = args.rect
    else:
        roi = draw_roi_window(cam, frame) if has_gui() else None
        if roi is None:
            # No screen (e.g. inside Docker): save a gridded frame to read the box off instead.
            grid = DATA_DIR / "snapshots" / f"{cam.name}_grid_{stamp()}.jpg"
            grid.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(grid), draw_grid(frame))
            print(f"\nNo window available to draw in. Open this image instead:\n  {rel(grid)}\n"
                  "Grid lines are every 0.1 of the width/height. Read off the box around the flow\n"
                  "(left edge x, top edge y, width w, height h) and run roi again with it, e.g.:\n"
                  f"  roi --camera {cam.name} --rect 0.60,0.10,0.25,0.25")
            return 1
        if roi == ():
            print("No region drawn — nothing saved.")
            return 1

    config.save_roi(cam.name, roi, (w, h))
    cam.roi = roi
    print(f"Saved ROI for {cam.name} to {rel(config.ROIS_FILE)}: {[round(v, 4) for v in roi]}")
    print(f"Preview → {rel(save_snapshot(cam, frame, 'roi'))}")
    return 0


# ---------------------------------------------------------------- collect

def cmd_collect(args) -> int:
    cams = config.load_cameras(args.camera)
    ffmpeg_path()
    for cam in cams:
        cam.password  # noqa: B018 — fail fast on a missing password
    session = f"collect-{stamp()}"
    print(f"Collecting {args.duration:g}s every {args.interval:g}s from {', '.join(c.name for c in cams)} "
          f"(session {session}). Ctrl+C to stop.\nManifest: {rel(MANIFEST)}\n")

    stats = {c.name: {"attempts": 0, "ok": 0, "fail_streak": 0} for c in cams}
    next_due = {c.name: 0.0 for c in cams}
    try:
        while True:
            for cam in cams:
                if time.monotonic() < next_due[cam.name]:
                    continue
                s = stats[cam.name]
                s["attempts"] += 1
                row = capture(cam, args.duration, session, args.label, args.notes, audio=not args.no_audio)
                ts = datetime.now().strftime("%H:%M:%S")
                if row["status"] == "error":
                    s["fail_streak"] += 1
                    retry = min(args.interval, 30 * 2 ** (s["fail_streak"] - 1))
                    print(f"{ts} {cam.name:<16} ERROR  {row['error']}  (retry in {retry:g}s)", flush=True)
                    next_due[cam.name] = time.monotonic() + retry
                else:
                    if s["fail_streak"]:
                        print(f"{ts} {cam.name:<16} recovered after {s['fail_streak']} failed attempt(s)")
                    s["ok"] += 1
                    s["fail_streak"] = 0
                    roi = f"roi {row['motion_roi']:>7}" if row["motion_roi"] != "" else "roi     n/a"
                    flag = "  FROZEN" if row["status"] == "frozen" else ""
                    print(f"{ts} {cam.name:<16} ok  {'IR ' if row['ir_mode'] else 'day'}  {roi}  "
                          f"frame {row['motion_frame']:>7}  {row['fps']:>5}fps{flag}", flush=True)
                    next_due[cam.name] = time.monotonic() + args.interval
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")

    for name, s in stats.items():
        pct = 100 * s["ok"] / s["attempts"] if s["attempts"] else 0
        print(f"{name}: {s['ok']}/{s['attempts']} attempts succeeded ({pct:.1f}%)")
    return 0 if all(s["ok"] == s["attempts"] for s in stats.values()) else 1


# ---------------------------------------------------------------- staged

def cmd_staged(args) -> int:
    cams = config.load_cameras([args.camera] if args.camera else None)
    if len(cams) > 1:
        sys.exit(f"Several cameras configured — pick one with --camera ({', '.join(c.name for c in cams)})")
    cam = cams[0]
    ffmpeg_path()
    cam.password  # noqa: B018
    session = f"staged-{stamp()}"
    if not cam.roi:
        print("Note: no ROI set yet, so only whole-frame motion will be shown. "
              "Clips are still saved and can be re-scored once the ROI exists.\n")

    print(f"Staged outage on the {cam.tank} tank ({cam.name}), session {session}.\n"
          f"The filter will be off for about {args.settle + args.stopped:g} seconds.\n")

    def step(prompt: str, label: str, seconds: float) -> dict | None:
        input(f"{prompt}  Press ENTER when ready… ")
        print(f"  recording {seconds:g}s labeled '{label}'…", flush=True)
        row = capture(cam, seconds, session, label, args.notes)
        if row["status"] == "error":
            print(f"  ERROR: {row['error']}")
            return None
        motion = row["motion_roi"] if row["motion_roi"] != "" else row["motion_frame"]
        print(f"  saved {row['file']}  ({'IR' if row['ir_mode'] else 'day'}, motion {motion})")
        return row

    running = step("1/3  Filter running normally.", "running", args.baseline)
    input("2/3  UNPLUG the filter now.  Press ENTER once it is off… ")
    if args.settle:
        print(f"  waiting {args.settle:g}s for the water to settle…", flush=True)
        time.sleep(args.settle)
    print(f"  recording {args.stopped:g}s labeled 'stopped'…", flush=True)
    stopped = capture(cam, args.stopped, session, "stopped", args.notes)
    if stopped["status"] == "error":
        print(f"  ERROR: {stopped['error']}")
        stopped = None
    else:
        m = stopped["motion_roi"] if stopped["motion_roi"] != "" else stopped["motion_frame"]
        print(f"  saved {stopped['file']}  ({'IR' if stopped['ir_mode'] else 'day'}, motion {m})")
    step("3/3  PLUG the filter back in.", "restarting", args.restart)

    print("\nCheck the filter has restarted and re-primed before you walk away.")
    if running and stopped:
        key = "motion_roi" if running["motion_roi"] != "" else "motion_frame"
        r, s = float(running[key]), float(stopped[key])
        ratio = f"{r / s:.1f}x" if s > 0 else "∞"
        print(f"\n{key}: running {r:g} vs stopped {s:g}  → running is {ratio} the stopped level")
        if s >= r:
            print("Stopped looks as busy as running in this region — the ROI may be on the wrong "
                  "spot, or other motion (airstone, fish, light) dominates. Worth a look.")
    return 0 if running and stopped else 1


# ---------------------------------------------------------------- main

def _stop_on_sigterm(signum, frame):
    raise KeyboardInterrupt  # same clean shutdown as Ctrl+C when a service manager stops us


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m filter_monitor",
                                description="Filter Monitor — Phase 1A: connect & collect")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="test the connection to each camera")
    c.add_argument("--camera", action="append", help="camera name (repeatable); default all")
    c.add_argument("--seconds", type=float, default=5, help="test clip length (default 5)")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("roi", help="draw the flow region for a camera")
    r.add_argument("--camera", help="camera name (needed if more than one is configured)")
    r.add_argument("--rect", type=parse_rect, help="skip the window: x,y,w,h as frame fractions")
    r.set_defaults(func=cmd_roi)

    k = sub.add_parser("collect", help="sample short clips on a schedule (unattended)")
    k.add_argument("--camera", action="append", help="camera name (repeatable); default all")
    k.add_argument("--interval", type=float, default=300, help="seconds between clips (default 300)")
    k.add_argument("--duration", type=float, default=10, help="clip length in seconds (default 10)")
    k.add_argument("--label", default="assumed_running",
                   help="label for these clips (default assumed_running)")
    k.add_argument("--notes", default="", help="free text stored with each clip")
    k.add_argument("--no-audio", action="store_true", help="drop the audio track")
    k.add_argument("--once", action="store_true", help="one clip per camera, then exit")
    k.set_defaults(func=cmd_collect)

    s = sub.add_parser("staged", help="guided staged outage: running → stopped → restarting")
    s.add_argument("--camera", help="camera name (needed if more than one is configured)")
    s.add_argument("--baseline", type=float, default=60, help="running clip seconds (default 60)")
    s.add_argument("--settle", type=float, default=10, help="wait after unplugging (default 10)")
    s.add_argument("--stopped", type=float, default=120, help="stopped clip seconds (default 120)")
    s.add_argument("--restart", type=float, default=60, help="restarting clip seconds (default 60)")
    s.add_argument("--notes", default="", help="e.g. 'day, lights on' or 'night, IR'")
    s.set_defaults(func=cmd_staged)

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # never crash on a console that can't print → or …
    args = p.parse_args(argv)
    signal.signal(signal.SIGTERM, _stop_on_sigterm)
    try:
        return args.func(args)
    except (ConfigError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
