#!/usr/bin/env python3
"""Generate an original CC0 cozy music bed (no third-party samples)."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 22050
DURATION = 16.0


def envelope(t: float, dur: float, attack: float = 0.03, release: float = 0.12) -> float:
    if t < attack:
        return t / attack
    if t > dur - release:
        return max(0.0, (dur - t) / release)
    return 1.0


def tone(t: float, freq: float, amp: float) -> float:
    return amp * math.sin(2 * math.pi * freq * t)


def generate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(RATE * DURATION)
    # Gentle C-major pentatonic arpeggio + soft fifth pad.
    melody = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63, 293.66, 261.63]
    samples = []
    for i in range(n):
        t = i / RATE
        beat = 0.5
        idx = int(t / beat) % len(melody)
        local = t % beat
        lead = tone(t, melody[idx], 0.18) * envelope(local, beat, 0.02, 0.18)
        pad = (
            tone(t, 130.81, 0.08)
            + tone(t, 196.00, 0.05)
            + tone(t, 329.63, 0.03)
        ) * (0.7 + 0.3 * math.sin(2 * math.pi * 0.125 * t))
        # Very soft noise shaker on 8ths
        tick = 0.0
        if local < 0.03 and int(t / (beat / 2)) % 2 == 0:
            tick = ((i * 1103515245 + 12345) % 1000) / 1000.0 * 0.03
        s = max(-1.0, min(1.0, lead + pad + tick))
        samples.append(int(s * 32767))

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "assets" / "music" / "cozy_afternoon.wav")
