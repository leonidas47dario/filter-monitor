"""Network side (ffmpeg pulls clips off the camera) and analysis side (OpenCV reads local clips).

Keeping all camera I/O in ffmpeg means RTSPS, reconnect timeouts and odd codecs are
handled by one well-tested tool; OpenCV only ever opens local files.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import Camera

SOCKET_TIMEOUT_S = 10
ANALYSIS_WIDTH = 960  # downscale before measuring motion; plenty for an ROI
IR_SATURATION_MAX = 12  # mean HSV saturation below this ≈ black-and-white IR night mode


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (Windows: `winget install Gyan.FFmpeg`, "
            "macOS: `brew install ffmpeg`, Linux: `apt install ffmpeg`) and open a new terminal."
        )
    return path


def tcp_reachable(cam: Camera, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((cam.host, cam.port), timeout=timeout):
            return True, f"{cam.host}:{cam.port} accepts connections"
    except OSError as e:
        return False, f"{cam.host}:{cam.port} not reachable ({e.__class__.__name__}: {e})"


@dataclass
class RecordResult:
    ok: bool
    path: Path | None
    error: str = ""


def record_clip(cam: Camera, out_path: Path, duration_s: float, audio: bool = True) -> RecordResult:
    """Copy `duration_s` seconds of the live stream to a Matroska file, without re-encoding."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    part = out_path.with_name(out_path.name + ".part")
    cmd = [
        ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-rtsp_transport", "tcp",
        "-timeout", str(SOCKET_TIMEOUT_S * 1_000_000),
        "-i", cam.stream_url(),
        "-t", f"{duration_s:g}",
        "-map", "0:v:0",
    ]
    if audio:
        cmd += ["-map", "0:a?"]
    cmd += ["-c", "copy", "-f", "matroska", "-y", str(part)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              timeout=duration_s + 3 * SOCKET_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        part.unlink(missing_ok=True)
        return RecordResult(False, None, "ffmpeg timed out (stream stalled)")
    except KeyboardInterrupt:
        part.unlink(missing_ok=True)
        raise

    if proc.returncode != 0 or not part.exists() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        tail = " | ".join(proc.stderr.strip().splitlines()[-3:]) or f"ffmpeg exit code {proc.returncode}"
        return RecordResult(False, None, cam.redact(tail))

    part.replace(out_path)
    return RecordResult(True, out_path)


@dataclass
class ClipStats:
    frames: int
    width: int
    height: int
    fps: float
    brightness: float
    ir_mode: bool
    motion_frame: float  # mean abs change between consecutive frames, whole frame (0-255 scale)
    motion_roi: float | None  # same, inside the ROI only
    dup_frac: float  # share of consecutive frame pairs that are pixel-identical
    middle_frame: np.ndarray | None

    @property
    def frozen(self) -> bool:
        return self.frames >= 2 and self.dup_frac >= 0.999


def roi_pixels(roi: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = roi
    x0, y0 = int(round(x * width)), int(round(y * height))
    x1, y1 = int(round((x + w) * width)), int(round((y + h) * height))
    x0, y0 = max(0, min(x0, width - 1)), max(0, min(y0, height - 1))
    x1, y1 = max(x0 + 1, min(x1, width)), max(y0 + 1, min(y1, height))
    return x0, y0, x1, y1


def analyze_clip(path: Path, roi: tuple[float, float, float, float] | None = None) -> ClipStats:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {path}")
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        reported_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0

        frames, dups = 0, 0
        frame_diffs, roi_diffs, brightness, saturation = [], [], [], []
        prev_gray, middle, first_ms, last_ms = None, None, None, 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames += 1
            ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            first_ms = ms if first_ms is None else first_ms
            last_ms = ms

            if frame.shape[1] > ANALYSIS_WIDTH:
                scale = ANALYSIS_WIDTH / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            middle = frame  # fallback snapshot if seeking to the middle fails below
            gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
            brightness.append(float(gray.mean()))
            if frames % 10 == 1:
                saturation.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[..., 1].mean()))

            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                if not diff.any():
                    dups += 1
                frame_diffs.append(float(diff.mean()))
                if roi:
                    x0, y0, x1, y1 = roi_pixels(roi, diff.shape[1], diff.shape[0])
                    roi_diffs.append(float(diff[y0:y1, x0:x1].mean()))
            prev_gray = gray
    finally:
        cap.release()

    if frames == 0:
        raise RuntimeError(f"No frames decoded from {path}")

    # Grab the true middle frame for the snapshot.
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frames // 2)
    ok, mid = cap.read()
    cap.release()
    if ok:
        middle = mid

    span_s = ((last_ms or 0) - (first_ms or 0)) / 1000
    fps = (frames - 1) / span_s if span_s > 0 else reported_fps
    pairs = max(frames - 1, 1)
    return ClipStats(
        frames=frames,
        width=width,
        height=height,
        fps=round(fps, 2),
        brightness=round(float(np.mean(brightness)), 1),
        ir_mode=bool(np.mean(saturation) < IR_SATURATION_MAX),
        motion_frame=round(float(np.mean(frame_diffs)), 4) if frame_diffs else 0.0,
        motion_roi=round(float(np.mean(roi_diffs)), 4) if roi_diffs else None,
        dup_frac=round(dups / pairs, 4),
        middle_frame=middle,
    )


def draw_roi(frame: np.ndarray, roi: tuple[float, float, float, float] | None) -> np.ndarray:
    if roi is None:
        return frame
    out = frame.copy()
    x0, y0, x1, y1 = roi_pixels(roi, out.shape[1], out.shape[0])
    cv2.rectangle(out, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 255), 2)
    return out
