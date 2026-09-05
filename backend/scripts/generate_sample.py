#!/usr/bin/env python3
"""Create a short vertical demo clip for offline Drive-mock inbox."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/inbox/sample-cat.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10_000:
        print(f"sample exists: {dest}")
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x2b1d14:s=1080x1920:d=8:r=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=330:sample_rate=48000:duration=8",
        "-filter_complex",
        (
            "[0:v]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            "text='Cat Shorts Demo':fontsize=72:fontcolor=0xF4EBE3:"
            "x=(w-text_w)/2:y=h*0.36,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            "text='sample-cat.mp4':fontsize=36:fontcolor=0xE8A87C:"
            "x=(w-text_w)/2:y=h*0.46,"
            "drawbox=x=390:y=1100:w=300:h=180:color=0xC45C26@0.85:t=fill[v]"
        ),
        "-map",
        "[v]",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    subprocess.run(cmd, check=True)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
