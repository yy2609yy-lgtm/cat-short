"""FFmpeg helpers: probe, crop math, render, technical check."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas import CropParams

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class MediaError(RuntimeError):
    pass


def run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise MediaError(f"command failed: {' '.join(cmd)}\n{proc.stderr[-2000:]}")
    return proc


def probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MediaError(f"file missing: {path}")
    proc = run(
        [
            FFPROBE,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    return json.loads(proc.stdout)


def video_meta(path: Path) -> dict[str, Any]:
    info = probe(path)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or 0)
    if video and not duration:
        duration = float(video.get("duration") or 0)
    return {
        "duration": duration,
        "width": int(video["width"]) if video and video.get("width") else None,
        "height": int(video["height"]) if video and video.get("height") else None,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "size_bytes": int(info.get("format", {}).get("size") or path.stat().st_size),
    }


def crop_fingerprint(crop: CropParams) -> str:
    raw = json.dumps(crop.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_crop_box(src_w: int, src_h: int, crop: CropParams) -> tuple[int, int, int, int]:
    """Largest 9:16 window on source, then zoom + pan around focus."""
    target_ratio = settings.render_width / settings.render_height  # 9/16
    if src_w / src_h > target_ratio:
        base_h = src_h
        base_w = int(round(base_h * target_ratio))
    else:
        base_w = src_w
        base_h = int(round(base_w / target_ratio))

    zoom = max(1.0, float(crop.zoom))
    w = max(2, int(round(base_w / zoom)) // 2 * 2)
    h = max(2, int(round(base_h / zoom)) // 2 * 2)
    # Keep 9:16 after even rounding
    if w / h > target_ratio:
        w = int(round(h * target_ratio)) // 2 * 2
    else:
        h = int(round(w / target_ratio)) // 2 * 2

    max_x = max(0, src_w - w)
    max_y = max(0, src_h - h)
    x = int(round(crop.focus_x * max_x))
    y = int(round(crop.focus_y * max_y))
    x = min(max(0, x), max_x)
    y = min(max(0, y), max_y)
    return x, y, w, h


def write_ass(srt_path: Path, ass_path: Path, font_path: Path) -> None:
    """Convert SRT to a simple ASS with large bottom-centered English captions."""
    font_name = "DejaVu Sans"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {settings.render_width}
PlayResY: {settings.render_height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},64,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,70,70,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    blocks = srt_path.read_text(encoding="utf-8").strip().split("\n\n")
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        start, end = lines[1].split(" --> ")
        text = "\\N".join(lines[2:]).replace("\n", "\\N")
        events.append(f"Dialogue: 0,{_srt_to_ass(start)},{_srt_to_ass(end)},Default,,0,0,0,,{text}")
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    _ = font_path  # reserved for fontsdir; DejaVu is the default in the image


def _srt_to_ass(ts: str) -> str:
    # 00:00:01,000 -> 0:00:01.00
    ts = ts.strip().replace(",", ".")
    h, m, rest = ts.split(":")
    sec, ms = rest.split(".")
    cs = int(round(int(ms[:3].ljust(3, "0")) / 10))
    return f"{int(h)}:{m}:{sec}.{cs:02d}"


def render_vertical(
    src: Path,
    dest: Path,
    crop: CropParams,
    srt_path: Path,
    music_path: Path,
    work_dir: Path,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    meta = video_meta(src)
    src_w = meta["width"] or settings.render_width
    src_h = meta["height"] or settings.render_height
    duration = min(max(0.2, crop.end - crop.start), settings.render_max_seconds)
    x, y, w, h = compute_crop_box(src_w, src_h, crop)

    ass_path = work_dir / "captions.ass"
    write_ass(srt_path, ass_path, settings.caption_font_path)
    # Escape for ffmpeg filter (windows-style colon escaping)
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

    vf = (
        f"crop={w}:{h}:{x}:{y},"
        f"scale={settings.render_width}:{settings.render_height}:flags=lanczos,"
        f"fps={settings.render_fps},"
        f"ass='{ass_escaped}'"
    )

    has_audio = bool(meta.get("audio_codec"))
    cmd = [FFMPEG, "-y", "-ss", f"{crop.start:.3f}", "-t", f"{duration:.3f}", "-i", str(src)]
    if music_path.exists():
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]
        if has_audio:
            # Original voice stays primary; bed sits underneath.
            filter_complex = (
                f"[0:v]{vf}[v];"
                f"[0:a]volume=1.0[va];"
                f"[1:a]volume=0.18,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[bed];"
                f"[va][bed]amix=inputs=2:duration=first:dropout_transition=0,"
                f"alimiter=limit=0.95[a]"
            )
        else:
            filter_complex = (
                f"[0:v]{vf}[v];"
                f"[1:a]volume=0.28,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[a]"
            )
        cmd += [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]
    else:
        cmd += ["-vf", vf]
        if has_audio:
            cmd += ["-map", "0:a"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-t",
        f"{duration:.3f}",
        str(dest),
    ]
    run(cmd, timeout=600)


def technical_check(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "ok": False,
        "errors": [],
    }
    if not path.exists():
        report["errors"].append("render file does not exist")
        return report
    try:
        meta = video_meta(path)
    except MediaError as exc:
        report["errors"].append(f"not decodable: {exc}")
        return report

    report.update(meta)
    if meta.get("video_codec") != "h264":
        report["errors"].append(f"video codec {meta.get('video_codec')} != h264")
    if meta.get("audio_codec") not in {"aac", "mp4a"}:
        report["errors"].append(f"audio codec {meta.get('audio_codec')} not aac")
    if meta.get("width") != settings.render_width or meta.get("height") != settings.render_height:
        report["errors"].append(
            f"resolution {meta.get('width')}x{meta.get('height')} != "
            f"{settings.render_width}x{settings.render_height}"
        )
    if (meta.get("duration") or 0) <= 0.2:
        report["errors"].append("duration too short")
    if (meta.get("duration") or 0) > settings.render_max_seconds + 1.5:
        report["errors"].append(f"duration {meta.get('duration')} exceeds max")
    report["ok"] = len(report["errors"]) == 0
    return report
