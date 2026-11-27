// ---------- Schema (created by init_db.py) ----------
// (Artist)-[:PERFORMED]->(Song)-[:IN_ALBUM]->(Album)-[:ALBUM_GENRE]->(Genre)-[:TYPICALLY_FEELS]->(Mood)
// (Song)-[:HAS_GENRE]->(Genre)  (Song)-[:HAS_MOOD]->(Mood)  (Song)-[:IN_LANGUAGE]->(Language)
// (Artist)-[:RELEASED]->(Album)  (Artist)-[:PLAYS_GENRE]->(Genre)
// (User)-[:LIKED {at}]->(Song)   (User)-[:PLAYED {at}]->(Song)
// (User)-[:OWNS]->(Playlist)-[:CONTAINS {added}]->(Song)   (Session)-[:OF_USER]->(User)

// See the whole music graph (in Neo4j Browser, http://localhost:7474)
MATCH p=(a:Artist)-[:PERFORMED]->(:Song)-[:IN_ALBUM]->(:Album)-[:ALBUM_GENRE]->(:Genre)-[:TYPICALLY_FEELS]->(:Mood)
RETURN p LIMIT 100;

// Songs most similar (by shared graph nodes) to a given song
MATCH (s:Song {title:'Blinding Lights'})-[:HAS_GENRE|HAS_MOOD|IN_LANGUAGE|IN_ALBUM|PERFORMED]-(x)
      -[:HAS_GENRE|HAS_MOOD|IN_LANGUAGE|IN_ALBUM|PERFORMED]-(c:Song)
WHERE c <> s
RETURN c.title AS song, count(DISTINCT x) AS shared, collect(DISTINCT x.name) AS via
ORDER BY shared DESC LIMIT 10;

// Collaborative: what else do people who liked/played a song listen to?
MATCH (s:Song {title:'Believer'})<-[:LIKED|PLAYED]-(u:User)-[:LIKED|PLAYED]->(c:Song)
WHERE c <> s RETURN c.title, count(DISTINCT u) AS users ORDER BY users DESC;

// A user's listening history and likes
MATCH (u:User {username:'demo'})-[r:PLAYED]->(s:Song) RETURN s.title, r.at ORDER BY r.at DESC LIMIT 20;
MATCH (u:User {username:'demo'})-[:LIKED]->(s:Song) RETURN s.title;

// Counts
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;

// Reset only user activity (keeps songs)
MATCH ()-[r:LIKED|PLAYED]->() DELETE r;
