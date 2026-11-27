"""Scan songs/ for audio files and add any that are not yet in music.csv.

    python import_songs.py                       # read tags (title/artist/album/genre) via mutagen
    python import_songs.py --language Hindi      # default language for the new rows
    python import_songs.py --analyze             # optional: estimate tempo/energy/danceability (pip install librosa)
    python init_db.py                            # then load the new rows into Neo4j

File names like "Artist - Title.mp3" are used when a file has no tags.
Afterwards open music.csv and fix mood / language / popularity for best recommendations.
"""
import argparse
import csv
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
COLS = ["song", "artist", "album", "genre", "mood", "language", "energy", "danceability",
        "popularity", "tempo", "audio_file", "spotify_id"]


def read_tags(path):
    tags = {}
    try:
        import mutagen
        f = mutagen.File(path, easy=True)
        if f and f.tags:
            for k in ("title", "artist", "album", "genre"):
                if f.tags.get(k):
                    tags[k] = str(f.tags[k][0]).strip()
    except Exception:
        pass
    stem = re.sub(r"[_]+", " ", path.stem).strip()
    if "title" not in tags:
        if " - " in stem:
            a, t = stem.split(" - ", 1)
            tags.setdefault("artist", a.strip())
            tags["title"] = t.strip()
        else:
            tags["title"] = stem
    return tags


def analyze(path):
    """Rough audio features with librosa (optional). Returns dict or {}."""
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(str(path), duration=90)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])
        energy = float(min(1.0, np.sqrt(np.mean(y ** 2)) * 4))
        ibi = np.diff(librosa.frames_to_time(beats, sr=sr))
        dance = float(1 - min(1.0, (ibi.std() / ibi.mean()) * 3)) if len(ibi) > 4 else 0.5
        return {"tempo": round(tempo), "energy": round(energy, 2), "danceability": round(max(dance, 0.1), 2)}
    except Exception as exc:
        print(f"  (analysis skipped: {exc})")
        return {}


def guess_mood(energy):
    return "Energetic" if energy > 0.75 else "Happy" if energy > 0.5 else "Chill" if energy > 0.3 else "Peaceful"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--language", default="English")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()

    csv_path = BASE / "music.csv"
    df = pd.read_csv(csv_path, dtype=str).fillna("") if csv_path.exists() else pd.DataFrame(columns=COLS)
    known = set(df.get("audio_file", []))
    new_rows = []
    for path in sorted((BASE / "songs").iterdir()):
        if path.suffix.lower() not in EXTS or path.name in known:
            continue
        tags = read_tags(path)
        feat = analyze(path) if args.analyze else {}
        energy = feat.get("energy", 0.5)
        new_rows.append({
            "song": tags["title"], "artist": tags.get("artist", "Unknown Artist"),
            "album": tags.get("album", "Single"), "genre": tags.get("genre", "Unknown"),
            "mood": guess_mood(energy), "language": args.language,
            "energy": energy, "danceability": feat.get("danceability", 0.5),
            "popularity": 50, "tempo": feat.get("tempo", 100), "audio_file": path.name, "spotify_id": "",
        })
        print("+", tags["title"], "-", tags.get("artist", "Unknown Artist"))
    if not new_rows:
        print("No new audio files found in songs/.")
        return
    out = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)[COLS]
    out.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"Added {len(new_rows)} song(s). Now run:  python init_db.py   (then restart Streamlit)")


if __name__ == "__main__":
    main()
