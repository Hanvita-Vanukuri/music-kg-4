"""User-owned data in Neo4j: likes, play history, playlists, stats."""
import uuid

from . import db


# ---------- likes ----------
def like(username, song_id):
    db.run(
        "MATCH (u:User {username:$u}), (s:Song {song_id:$id}) "
        "MERGE (u)-[r:LIKED]->(s) ON CREATE SET r.at = datetime()",
        u=username, id=song_id,
    )


def unlike(username, song_id):
    db.run("MATCH (:User {username:$u})-[r:LIKED]->(:Song {song_id:$id}) DELETE r", u=username, id=song_id)


def liked_ids(username):
    rows = db.run(
        "MATCH (:User {username:$u})-[r:LIKED]->(s:Song) RETURN s.song_id AS song_id ORDER BY r.at DESC",
        u=username,
    )
    return [r["song_id"] for r in rows]


# ---------- listening history ----------
def record_play(username, song_id):
    db.run(
        "MATCH (u:User {username:$u}), (s:Song {song_id:$id}) CREATE (u)-[:PLAYED {at: datetime()}]->(s)",
        u=username, id=song_id,
    )


def recent_plays(username, limit=30):
    """Distinct songs, newest first, with play counts."""
    return db.run(
        "MATCH (:User {username:$u})-[p:PLAYED]->(s:Song) "
        "WITH s, max(p.at) AS last, count(p) AS n ORDER BY last DESC LIMIT $limit "
        "RETURN s.song_id AS song_id, toString(last) AS last_played, n",
        u=username, limit=limit,
    )


# ---------- playlists ----------
def create_playlist(username, name):
    pid = uuid.uuid4().hex[:12]
    db.run(
        "MATCH (u:User {username:$u}) "
        "CREATE (u)-[:OWNS]->(:Playlist {pid:$pid, name:$name, created_at: datetime()})",
        u=username, pid=pid, name=name.strip(),
    )
    return pid


def list_playlists(username):
    return db.run(
        "MATCH (:User {username:$u})-[:OWNS]->(p:Playlist) "
        "OPTIONAL MATCH (p)-[:CONTAINS]->(s:Song) "
        "WITH p, count(s) AS n ORDER BY p.created_at DESC "
        "RETURN p.pid AS pid, p.name AS name, n",
        u=username,
    )


def playlist_song_ids(username, pid):
    rows = db.run(
        "MATCH (:User {username:$u})-[:OWNS]->(:Playlist {pid:$pid})-[r:CONTAINS]->(s:Song) "
        "RETURN s.song_id AS song_id ORDER BY r.added",
        u=username, pid=pid,
    )
    return [r["song_id"] for r in rows]


def add_to_playlist(username, pid, song_id):
    rows = db.run(
        "MATCH (:User {username:$u})-[:OWNS]->(p:Playlist {pid:$pid}), (s:Song {song_id:$id}) "
        "MERGE (p)-[r:CONTAINS]->(s) ON CREATE SET r.added = datetime() RETURN count(r) AS c",
        u=username, pid=pid, id=song_id,
    )
    return bool(rows and rows[0]["c"])


def remove_from_playlist(username, pid, song_id):
    db.run(
        "MATCH (:User {username:$u})-[:OWNS]->(:Playlist {pid:$pid})-[r:CONTAINS]->(:Song {song_id:$id}) DELETE r",
        u=username, pid=pid, id=song_id,
    )


def delete_playlist(username, pid):
    db.run("MATCH (:User {username:$u})-[:OWNS]->(p:Playlist {pid:$pid}) DETACH DELETE p", u=username, pid=pid)


# ---------- profile stats ----------
def user_stats(username):
    rows = db.run(
        "MATCH (u:User {username:$u}) "
        "OPTIONAL MATCH (u)-[:LIKED]->(l:Song) WITH u, count(DISTINCT l) AS likes "
        "OPTIONAL MATCH (u)-[p:PLAYED]->(:Song) WITH u, likes, count(p) AS plays "
        "OPTIONAL MATCH (u)-[:OWNS]->(pl:Playlist) "
        "RETURN likes, plays, count(DISTINCT pl) AS playlists, toString(u.created_at) AS joined",
        u=username,
    )
    return rows[0] if rows else {"likes": 0, "plays": 0, "playlists": 0, "joined": ""}


def top_genres(username, limit=6):
    return db.run(
        "MATCH (:User {username:$u})-[:PLAYED]->(:Song)-[:HAS_GENRE]->(g:Genre) "
        "RETURN g.name AS name, count(*) AS n ORDER BY n DESC LIMIT $limit",
        u=username, limit=limit,
    )


def top_artists(username, limit=6):
    return db.run(
        "MATCH (:User {username:$u})-[:PLAYED]->(:Song)<-[:PERFORMED]-(a:Artist) "
        "RETURN a.name AS name, count(*) AS n ORDER BY n DESC LIMIT $limit",
        u=username, limit=limit,
    )
