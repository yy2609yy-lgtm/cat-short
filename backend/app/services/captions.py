"""Caption/music contract implementation (no AI station required).

Input: cropped-confirmed vertical clip metadata (duration).
Output: English SRT with 3–6 short lines, later burned in by FFmpeg + CC0 bed.

A later AI handoff can replace `build_english_captions()` with a model that
returns the same SRT shape. Do not change the FFmpeg burn-in path.
"""

from __future__ import annotations

from pathlib import Path

# Short, generic English lines suitable for personal cat shorts.
# Not generated from video content — a deterministic fallback so render
# works offline. Replace this function for AI captions later.
FALLBACK_LINES = [
    "Look at this little cat.",
    "Soft paws, big personality.",
    "A tiny moment of joy.",
    "Curious eyes, cozy day.",
    "Stay cute. Stay curious.",
    "That's our star.",
]


def pick_lines(duration: float) -> list[str]:
    if duration <= 8:
        count = 3
    elif duration <= 20:
        count = 4
    elif duration <= 40:
        count = 5
    else:
        count = 6
    return FALLBACK_LINES[:count]


def format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_english_captions(duration: float) -> str:
    """Return SRT text: 3–6 short English lines spanning the clip."""
    duration = max(1.0, duration)
    lines = pick_lines(duration)
    slot = duration / len(lines)
    blocks = []
    for i, text in enumerate(lines):
        start = i * slot
        end = duration if i == len(lines) - 1 else (i + 1) * slot
        # Leave a tiny gap so cues don't overlap on burn-in.
        end = max(start + 0.4, end - 0.08)
        blocks.append(f"{i + 1}\n{format_ts(start)} --> {format_ts(end)}\n{text}\n")
    return "\n".join(blocks)


def write_srt(path: Path, duration: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_english_captions(duration), encoding="utf-8")
    return path
