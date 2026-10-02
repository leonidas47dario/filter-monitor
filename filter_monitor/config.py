"""Camera configuration: config/cameras.yaml plus passwords from .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMERAS_FILE = REPO_ROOT / "config" / "cameras.yaml"
ROIS_FILE = REPO_ROOT / "config" / "rois.yaml"
DATA_DIR = REPO_ROOT / "data"


class ConfigError(Exception):
    pass


@dataclass
class Camera:
    name: str
    tank: str
    model: str
    protocol: str
    host: str
    port: int
    path: str
    username: str
    password_env: str
    roi: tuple[float, float, float, float] | None = None  # normalized x, y, w, h
    _password: str | None = field(default=None, repr=False)

    @property
    def password(self) -> str:
        if self._password is None:
            value = os.environ.get(self.password_env, "")
            if not value:
                raise ConfigError(
                    f"{self.name}: no password found. Set {self.password_env}=... in "
                    f"{REPO_ROOT / '.env'} (copy .env.example to .env first)."
                )
            self._password = value
        return self._password

    def stream_url(self) -> str:
        user = quote(self.username, safe="")
        pw = quote(self.password, safe="")
        return f"{self.protocol}://{user}:{pw}@{self.host}:{self.port}{self.path}"

    def redact(self, text: str) -> str:
        """Strip the password (raw and URL-encoded) from any text before it is shown."""
        if self._password:
            for secret in {self._password, quote(self._password, safe="")}:
                text = text.replace(secret, "****")
        return text


def load_cameras(names: list[str] | None = None) -> list[Camera]:
    load_dotenv(REPO_ROOT / ".env")
    if not CAMERAS_FILE.exists():
        raise ConfigError(f"Missing {CAMERAS_FILE}")
    raw = yaml.safe_load(CAMERAS_FILE.read_text(encoding="utf-8")) or {}
    rois = load_rois()

    cameras = []
    for entry in raw.get("cameras") or []:
        try:
            cam = Camera(
                name=entry["name"],
                tank=str(entry.get("tank", "")),
                model=str(entry.get("model", "")),
                protocol=entry.get("protocol", "rtsp"),
                host=entry["host"],
                port=int(entry.get("port", 554)),
                path=entry.get("path", "/"),
                username=str(entry["username"]),
                password_env=entry["password_env"],
            )
        except KeyError as e:
            raise ConfigError(f"Camera entry {entry.get('name', '?')} is missing {e}") from None
        if cam.name in rois:
            cam.roi = tuple(rois[cam.name])
        cameras.append(cam)

    if names:
        unknown = set(names) - {c.name for c in cameras}
        if unknown:
            raise ConfigError(f"Unknown camera(s): {', '.join(sorted(unknown))}")
        cameras = [c for c in cameras if c.name in names]
    if not cameras:
        raise ConfigError(f"No cameras configured in {CAMERAS_FILE}")
    return cameras


def load_rois() -> dict[str, list[float]]:
    if not ROIS_FILE.exists():
        return {}
    raw = yaml.safe_load(ROIS_FILE.read_text(encoding="utf-8")) or {}
    return {name: v["roi"] for name, v in raw.items() if v and "roi" in v}


def save_roi(camera: str, roi: tuple[float, float, float, float], frame_size: tuple[int, int]) -> None:
    raw = {}
    if ROIS_FILE.exists():
        raw = yaml.safe_load(ROIS_FILE.read_text(encoding="utf-8")) or {}
    raw[camera] = {
        "roi": [round(v, 4) for v in roi],
        "drawn_on": f"{frame_size[0]}x{frame_size[1]}",
    }
    header = (
        "# Per-camera flow region (ROI), written by `python -m filter_monitor roi`.\n"
        "# roi = [x, y, width, height] as fractions of the frame, so it survives\n"
        "# resolution changes (e.g. switching to a bridge or substream).\n"
    )
    ROIS_FILE.write_text(header + yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
