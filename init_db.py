"""Create constraints and load music.csv into Neo4j as a knowledge graph.

    python init_db.py            # idempotent: safe to re-run (MERGE)
    python init_db.py --reset    # delete the music graph first (users/likes/history of those songs are lost)
    python init_db.py --wipe     # delete EVERYTHING in the database first
"""
import re
import sys

import pandas as pd

from core import db
from core.catalog import DERIVE, LOAD, slug, spotify_track_id
from core.config import CSV_PATH

CONSTRAINTS = [
    "CREATE CONSTRAINT song_id IF NOT EXISTS FOR (n:Song) REQUIRE n.song_id IS UNIQUE",
    "CREATE CONSTRAINT artist_name IF NOT EXISTS FOR (n:Artist) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT album_id IF NOT EXISTS FOR (n:Album) REQUIRE n.album_id IS UNIQUE",
    "CREATE CONSTRAINT genre_name IF NOT EXISTS FOR (n:Genre) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT mood_name IF NOT EXISTS FOR (n:Mood) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT language_name IF NOT EXISTS FOR (n:Language) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT user_name IF NOT EXISTS FOR (n:User) REQUIRE n.username IS UNIQUE",
    "CREATE CONSTRAINT playlist_id IF NOT EXISTS FOR (n:Playlist) REQUIRE n.pid IS UNIQUE",
    "CREATE CONSTRAINT session_token IF NOT EXISTS FOR (n:Session) REQUIRE n.token IS UNIQUE",
    "CREATE INDEX song_title IF NOT EXISTS FOR (n:Song) ON (n.title)",
]

def load_dataframe():
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    need = ["song", "artist", "album", "genre", "mood", "language", "energy", "danceability", "popularity", "tempo"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        sys.exit(f"music.csv is missing columns: {missing}")
    if "audio_file" not in df.columns:
        df["audio_file"] = ""
    if "spotify_id" not in df.columns:
        df["spotify_id"] = ""
    df["spotify_id"] = df["spotify_id"].map(spotify_track_id)
    for c in need[:6] + ["audio_file"]:
        df[c] = df[c].str.strip()
    for c in need[6:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in ("energy", "danceability"):
        if df[c].max() > 1:  # allow 0-100 scales
            df[c] = df[c] / 100.0
    df = df[(df["song"] != "") & (df["artist"] != "")]
    df["song_id"] = [slug(s, a) for s, a in zip(df["song"], df["artist"])]
    df["album_id"] = [slug(al or "single", a) for al, a in zip(df["album"], df["artist"])]
    df["album"] = df["album"].replace("", "Single")
    for c in ("genre", "mood", "language"):
        df[c] = df[c].replace("", "Unknown")
    return df.drop_duplicates("song_id").reset_index(drop=True)


def main():
    args = set(sys.argv[1:])
    db.get_driver()
    if "--wipe" in args:
        db.run("MATCH (n) DETACH DELETE n")
        print("Wiped entire database.")
    elif "--reset" in args:
        db.run("MATCH (n) WHERE n:Song OR n:Artist OR n:Album OR n:Genre OR n:Mood OR n:Language DETACH DELETE n")
        print("Deleted existing music graph.")
    for q in CONSTRAINTS:
        db.run(q)
    df = load_dataframe()
    rows = df.to_dict("records")
    for i in range(0, len(rows), 500):
        db.run(LOAD, rows=rows[i:i + 500])
    for q in DERIVE:
        db.run(q)
    counts = db.run(
        "MATCH (n) WHERE n:Song OR n:Artist OR n:Album OR n:Genre OR n:Mood OR n:Language "
        "RETURN labels(n)[0] AS label, count(n) AS n ORDER BY label"
    )
    print("Loaded", len(df), "songs.", {c["label"]: c["n"] for c in counts})


if __name__ == "__main__":
    main()
