"""Multi-factor recommendation engine.

final score (when a seed song is playing) =
    0.22 * content   numeric similarity  (energy, danceability, popularity, tempo)
  + 0.22 * categorical  artist 0.40 / genre 0.25 / mood 0.20 / language 0.15
  + 0.20 * graph     shared Neo4j neighbours (artist, album, genre, mood, language)
  + 0.10 * collab    other users who liked/played the seed also liked/played it
  + 0.20 * user      taste profile from likes (x3) + listening history (recency-weighted)
  + 0.06 * popularity
Recently played songs are demoted, and at most 3 songs per artist are returned.
Without a seed: 0.75 * user + 0.25 * popularity.
"""
import math

import numpy as np
import pandas as pd

from . import db, library

NUM_COLS = ["energy", "danceability", "popularity", "tempo"]
NUM_W = np.array([1.0, 1.0, 0.5, 0.6])
W_SEED = {"content": 0.22, "categorical": 0.22, "graph": 0.20, "collab": 0.10, "user": 0.20, "popularity": 0.06}
CAT_W = {"artist": 0.40, "genre": 0.25, "mood": 0.20, "language": 0.15}

SONGS_Q = """
MATCH (a:Artist)-[:PERFORMED]->(s:Song)-[:IN_ALBUM]->(al:Album)
MATCH (s)-[:HAS_GENRE]->(g:Genre)
MATCH (s)-[:HAS_MOOD]->(m:Mood)
MATCH (s)-[:IN_LANGUAGE]->(l:Language)
RETURN s.song_id AS song_id, s.title AS title, a.name AS artist, al.name AS album,
       g.name AS genre, m.name AS mood, l.name AS language,
       s.energy AS energy, s.danceability AS danceability,
       s.popularity AS popularity, s.tempo AS tempo, s.audio_file AS audio_file,
       s.spotify_id AS spotify_id
ORDER BY title
"""

# songs sharing artist / album / genre / mood / language nodes with the seed
GRAPH_Q = """
MATCH (s:Song {song_id:$id})-[:HAS_GENRE|HAS_MOOD|IN_LANGUAGE|IN_ALBUM|PERFORMED]-(x)
      -[:HAS_GENRE|HAS_MOOD|IN_LANGUAGE|IN_ALBUM|PERFORMED]-(c:Song)
WHERE c.song_id <> $id
RETURN c.song_id AS song_id, count(DISTINCT x) AS shared
"""

# collaborative signal: users who liked/played the seed also liked/played ...
COLLAB_Q = """
MATCH (s:Song {song_id:$id})<-[:LIKED|PLAYED]-(u:User)-[:LIKED|PLAYED]->(c:Song)
WHERE c.song_id <> $id AND u.username <> $me
RETURN c.song_id AS song_id, count(DISTINCT u) AS users
"""

PROFILE_Q = """
MATCH (:User {username:$u})-[r:LIKED|PLAYED]->(s:Song)
RETURN s.song_id AS song_id, type(r) AS t ORDER BY r.at DESC LIMIT 500
"""

_cache = {}


def refresh():
    """Drop the cached song table (call after adding songs)."""
    _cache.clear()


def get_songs():
    if "df" not in _cache:
        df = pd.DataFrame(db.run(SONGS_Q))
        if df.empty:
            raise RuntimeError("The music graph is empty. Run:  python init_db.py")
        for c in NUM_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        df["audio_file"] = df["audio_file"].fillna("")
        df["spotify_id"] = df["spotify_id"].fillna("")
        df = df.reset_index(drop=True)
        mn, mx = df[NUM_COLS].min(), df[NUM_COLS].max()
        norm = (df[NUM_COLS] - mn) / (mx - mn).replace(0, 1)
        _cache.update(df=df, norm=norm.to_numpy(float), pos={s: i for i, s in enumerate(df["song_id"])})
    return _cache["df"]


def get_song(song_id):
    df = get_songs()
    i = _cache["pos"].get(song_id)
    return None if i is None else df.iloc[i].to_dict()


def songs_by_ids(ids):
    df = get_songs()
    idx = [_cache["pos"][i] for i in ids if i in _cache["pos"]]
    return df.iloc[idx].reset_index(drop=True)


def trending(k=12):
    return get_songs().sort_values("popularity", ascending=False).head(k).reset_index(drop=True)


def _user_profile(username, df, norm):
    rows = db.run(PROFILE_Q, u=username)
    if not rows:
        return None
    weights = {}
    for i, r in enumerate(rows):  # newest first -> recency decay
        w = (3.0 if r["t"] == "LIKED" else 1.0) * (0.5 + 0.5 * math.exp(-i / 150))
        weights[r["song_id"]] = weights.get(r["song_id"], 0.0) + w
    w = df["song_id"].map(weights).fillna(0.0)
    if w.sum() == 0:
        return None
    aff = {}
    for col in ("artist", "genre", "mood", "language"):
        tot = pd.DataFrame({"k": df[col], "w": w}).groupby("k")["w"].sum()
        tot = tot / tot.max()
        aff[col] = df[col].map(tot).fillna(0.0).to_numpy(float)
    ed = norm[:, :2]
    centroid = (ed * w.to_numpy()[:, None]).sum(axis=0) / w.sum()
    closeness = 1 - np.sqrt(((ed - centroid) ** 2).mean(axis=1))
    score = (0.35 * aff["artist"] + 0.25 * aff["genre"] + 0.20 * aff["mood"]
             + 0.10 * aff["language"] + 0.10 * closeness)
    return {"score": np.clip(score, 0, 1), "aff": aff,
            "artists": set(df.loc[w > 0, "artist"])}


def recommend(username, seed_id=None, k=12, exclude_ids=(), novel_artists_only=False):
    """Return a DataFrame of up to k songs with columns: score, match, reason (+ song columns)."""
    df = get_songs()
    norm, pos = _cache["norm"], _cache["pos"]
    n = len(df)
    prof = _user_profile(username, df, norm)
    user = prof["score"] if prof else np.zeros(n)
    pop = norm[:, 2]
    seed_i = pos.get(seed_id) if seed_id else None

    graph = collab = content = cat = None
    if seed_i is not None:
        s = df.iloc[seed_i]
        dist = np.sqrt((((norm - norm[seed_i]) ** 2) * NUM_W).sum(axis=1) / NUM_W.sum())
        content = 1 - dist
        same = {c: (df[c] == s[c]).to_numpy(float) for c in CAT_W}
        cat = sum(CAT_W[c] * same[c] for c in CAT_W)
        graph = np.zeros(n)
        for r in db.run(GRAPH_Q, id=seed_id):
            if r["song_id"] in pos:
                graph[pos[r["song_id"]]] = min(r["shared"] / 5.0, 1.0)
        collab = np.zeros(n)
        rows = db.run(COLLAB_Q, id=seed_id, me=username)
        top = max([r["users"] for r in rows], default=0)
        for r in rows:
            if r["song_id"] in pos and top:
                collab[pos[r["song_id"]]] = r["users"] / top
        score = (W_SEED["content"] * content + W_SEED["categorical"] * cat + W_SEED["graph"] * graph
                 + W_SEED["collab"] * collab + W_SEED["user"] * user + W_SEED["popularity"] * pop)
    else:
        score = 0.75 * user + 0.25 * pop

    # demote what was just heard, remove excluded / seed / (optionally) known artists
    recent = {r["song_id"] for r in library.recent_plays(username, 8)}
    for sid in recent:
        if sid in pos and sid != seed_id:
            score[pos[sid]] -= 0.15
    banned = set(exclude_ids) | ({seed_id} if seed_id else set())
    for sid in banned:
        if sid in pos:
            score[pos[sid]] = -np.inf
    if novel_artists_only and prof:
        score[df["artist"].isin(prof["artists"]).to_numpy()] = -np.inf

    cap = 3 if k >= 6 else 2
    picked, per_artist = [], {}
    for i in np.argsort(-score):
        if not np.isfinite(score[i]) or len(picked) >= k:
            break
        a = df.at[i, "artist"]
        if per_artist.get(a, 0) >= cap:
            continue
        per_artist[a] = per_artist.get(a, 0) + 1
        picked.append(i)

    out = df.iloc[picked].copy()
    out["score"] = [float(score[i]) for i in picked]
    out["match"] = [int(max(1, min(99, round(score[i] * 100)))) for i in picked]
    reasons = []
    for i in picked:
        r = []
        if seed_i is not None:
            s = df.iloc[seed_i]
            if df.at[i, "artist"] == s["artist"]:
                r.append(f"Same artist: {s['artist']}")
            if df.at[i, "genre"] == s["genre"]:
                r.append(f"{s['genre']}")
            if df.at[i, "mood"] == s["mood"]:
                r.append(f"{s['mood']} mood")
            if df.at[i, "language"] == s["language"]:
                r.append(s["language"])
            if content[i] > 0.85:
                r.append("similar energy & beat")
            if collab[i] > 0:
                r.append("fans also play")
            if graph[i] >= 0.6 and not r:
                r.append("closely linked in graph")
        if prof:
            a = prof["aff"]
            if a["artist"][i] > 0.5:
                r.append("you like this artist")
            elif a["genre"][i] > 0.6:
                r.append(f"you listen to {df.at[i, 'genre']}")
        if not r:
            r.append("popular right now")
        reasons.append(" · ".join(r[:3]))
    out["reason"] = reasons
    return out.reset_index(drop=True)
