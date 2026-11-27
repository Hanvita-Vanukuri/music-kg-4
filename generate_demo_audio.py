"""Generate short synthetic demo tracks (WAV) for every row in music.csv -> songs/<audio_file>.

Real music: drop your own .mp3/.wav/.m4a/.ogg files into songs/ and put the file name in the
`audio_file` column of music.csv. Existing files are never overwritten.
"""
import argparse
import csv
import hashlib
import math
import struct
import wave
from pathlib import Path

BASE = Path(__file__).resolve().parent
SR, DUR = 11025, 12  # DUR can be raised with --minutes
MAJOR, MINOR = [0, 2, 4, 7, 9, 12], [0, 3, 5, 7, 10, 12]
SAD = {"Melancholic", "Dark", "Intense", "Dramatic", "Peaceful", "Chill"}


def synth(title, mood, tempo, energy):
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    root = 196.0 * 2 ** ((h % 12) / 12)
    scale = MINOR if mood in SAD else MAJOR
    bpm = float(tempo)
    while bpm > 140:
        bpm /= 2
    while bpm < 70:
        bpm *= 2
    step = 60.0 / bpm / 2
    n_steps = int(DUR / step)
    amp = 0.18 + 0.2 * float(energy)
    out = []
    for i in range(n_steps):
        deg = scale[(h >> (3 * (i % 10))) % len(scale)]
        f = root * 2 ** (deg / 12) * (2 if i % 8 == 7 else 1)
        n = int(step * SR)
        for j in range(n):
            t = j / SR
            env = min(1.0, j / 200) * math.exp(-3.0 * t / step)
            v = math.sin(2 * math.pi * f * t) + 0.4 * math.sin(4 * math.pi * f * t)
            v += 0.5 * math.sin(2 * math.pi * root / 2 * (i * step + t)) * (1 if i % 2 == 0 else 0.6)
            out.append(int(max(-1, min(1, amp * env * v / 1.9)) * 32000))
    return out


def main():
    global DUR
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=0, help='length per track (slow + large: ~4 MB/min)')
    ap.add_argument('--force', action='store_true', help='overwrite existing files')
    args = ap.parse_args()
    if args.minutes:
        DUR = int(args.minutes * 60)
    (BASE / "songs").mkdir(exist_ok=True)
    made = 0
    with open(BASE / "music.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("audio_file", "").strip()
            if not name.lower().endswith(".wav"):
                continue
            path = BASE / "songs" / name
            if path.exists() and not args.force:
                continue
            data = synth(row["song"], row["mood"], row["tempo"], row["energy"])
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(struct.pack(f"<{len(data)}h", *data))
            made += 1
    print(f"Created {made} demo audio files in songs/")


if __name__ == "__main__":
    main()