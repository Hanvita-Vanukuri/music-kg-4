"""Add / update songs without the terminal: audio -> songs/, rows -> music.csv, nodes -> Neo4j.
(No Streamlit import, so init_db.py can reuse LOAD / DERIVE / slug.)"""
import re
from pathlib import Path

import pandas as pd

from . import db
from .config import CSV_PATH, SONGS_DIR

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
COLS = ["song", "artist", "album", "genre", "mood", "language", "energy", "danceability",
        "popularity", "tempo", "audio_file", "spotify_id"]

LOAD = """
UNWIND $rows AS row
MERGE (s:Song {song_id: row.song_id})
  SET s.title = row.song, s.energy = row.energy, s.danceability = row.danceability,
      s.popularity = row.popularity, s.tempo = row.tempo, s.audio_file = row.audio_file,
      s.spotify_id = row.spotify_id
MERGE (a:Artist {name: row.artist})
MERGE (al:Album {album_id: row.album_id}) SET al.name = row.album
MERGE (g:Genre {name: row.genre})
MERGE (m:Mood {name: row.mood})
MERGE (l:Language {name: row.language})
MERGE (a)-[:PERFORMED]->(s)
MERGE (a)-[:RELEASED]->(al)
MERGE (s)-[:IN_ALBUM]->(al)
MERGE (s)-[:HAS_GENRE]->(g)
MERGE (s)-[:HAS_MOOD]->(m)
MERGE (s)-[:IN_LANGUAGE]->(l)
MERGE (a)-[:PLAYS_GENRE]->(g)
"""

# derived relationships (Album -> Genre -> Mood) used by the Knowledge Graph page
DERIVE = [
    "MATCH (s:Song)-[:IN_ALBUM]->(al:Album), (s)-[:HAS_GENRE]->(g:Genre) MERGE (al)-[:ALBUM_GENRE]->(g)",
    "MATCH (s:Song)-[:HAS_GENRE]->(g:Genre), (s)-[:HAS_MOOD]->(m:Mood) "
    "WITH g, m, count(s) AS n MERGE (g)-[r:TYPICALLY_FEELS]->(m) SET r.songs = n",
]


def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower()).strip("-")


def spotify_track_id(value):
    """Accept a Spotify track link / URI / bare 22-char id; return the id or ''."""
    v = (value or "").strip()
    m = re.search(r"track[/:]([A-Za-z0-9]{22})", v) or re.fullmatch(r"([A-Za-z0-9]{22})", v)
    return m.group(1) if m else ""


def _read_csv():
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("") if CSV_PATH.exists() else pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in df.columns:
            df[c] = ""
    return df


def _mask(df, song_id):
    return pd.Series([slug(s, a) == song_id for s, a in zip(df["song"], df["artist"])],
                     index=df.index, dtype=bool)


def save_audio(filename, data):
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        raise ValueError(f"Unsupported audio type {ext!r}. Use: {', '.join(sorted(AUDIO_EXTS))}")
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(filename).stem).strip(" ._") or "track"
    SONGS_DIR.mkdir(exist_ok=True)
    name, i = stem + ext, 2
    while (SONGS_DIR / name).exists():
        name, i = f"{stem}_{i}{ext}", i + 1
    (SONGS_DIR / name).write_bytes(data)
    return name


def add_song(meta, audio=None):
    """meta: song, artist, album, genre, mood, language, energy, danceability, popularity, tempo, spotify_id.
    audio: optional (filename, bytes). Updates songs/, music.csv and Neo4j. Returns the song_id."""
    title, artist = meta["song"].strip(), meta["artist"].strip()
    if not title or not artist:
        raise ValueError("Title and artist are required.")
    raw_link = (meta.get("spotify_id") or "").strip()
    spotify = spotify_track_id(raw_link)
    if raw_link and not spotify:
        raise ValueError("That doesn't look like a Spotify track link.")
    song_id = slug(title, artist)
    df = _read_csv()
    old = df[_mask(df, song_id)]
    audio_file = save_audio(*audio) if audio else (old.iloc[0]["audio_file"] if len(old) else "")
    if not audio_file and not spotify:
        raise ValueError("Upload an audio file or paste a Spotify link.")
    if not spotify and len(old):
        spotify = old.iloc[0]["spotify_id"]
    album = (meta.get("album") or "").strip()
    row = {"song": title, "artist": artist, "album": album or "Single",
           "genre": (meta.get("genre") or "").strip() or "Unknown",
           "mood": (meta.get("mood") or "").strip() or "Unknown",
           "language": (meta.get("language") or "").strip() or "Unknown",
           "energy": float(meta.get("energy", 0.5)), "danceability": float(meta.get("danceability", 0.5)),
           "popularity": float(meta.get("popularity", 50)), "tempo": float(meta.get("tempo", 100)),
           "audio_file": audio_file, "spotify_id": spotify}
    out = pd.concat([df[~_mask(df, song_id)], pd.DataFrame([row])], ignore_index=True)[COLS]
    out.to_csv(CSV_PATH, index=False)
    neo = dict(row, song_id=song_id, album_id=slug(album or "single", artist))
    db.run(LOAD, rows=[neo])
    for q in DERIVE:
        db.run(q)
    return song_id


def set_spotify(song_id, link):
    """Attach (or clear, with an empty link) a Spotify track on an existing song."""
    sp = spotify_track_id(link)
    if (link or "").strip() and not sp:
        raise ValueError("That doesn't look like a Spotify track link.")
    db.run("MATCH (s:Song {song_id:$id}) SET s.spotify_id = $sp", id=song_id, sp=sp)
    df = _read_csv()
    mask = _mask(df, song_id)
    if mask.any():
        df.loc[mask, "spotify_id"] = sp
        df[COLS].to_csv(CSV_PATH, index=False)


def bulk_set_spotify(text, songs_df):
    """Lines of 'Song title | spotify link'. Returns (updated_count, unmatched_lines)."""
    by_title = {}
    for r in songs_df.itertuples():
        by_title.setdefault(r.title.lower(), r.song_id)
    ok, missed = 0, []
    for line in text.splitlines():
        if "|" not in line:
            continue
        title, link = [x.strip() for x in line.split("|", 1)]
        sid = by_title.get(title.lower())
        if sid and spotify_track_id(link):
            set_spotify(sid, link)
            ok += 1
        else:
            missed.append(title or line)
    return ok, missed
