# MusicGraph: Spotify-style music knowledge graph (Python, Neo4j, Pandas, Streamlit)

## Setup (macOS), run each line separately (never paste the # comments)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Neo4j: either Docker (`docker compose up -d`) or Homebrew:
```bash
brew install neo4j
neo4j-admin dbms set-initial-password musicgraph123
neo4j start
```
(or a free cloud DB at neo4j.com/cloud/aura-free: put its URI/password in `.env`). Wait ~30 s, then:
```bash
python init_db.py
streamlit run app.py
```
Open http://localhost:8501, sign up, log in. Each new terminal: `source .venv/bin/activate` first.

## Adding songs (no terminal needed)
Sidebar -> **Add Songs**:
* upload a full-length mp3/wav/m4a/ogg/flac and fill in title, artist, album, genre, mood, language; and/or
* paste a Spotify track link (plays the full song through Spotify's embed when you are logged in to Spotify), or
* attach links to existing songs one by one, or in bulk (`Song title | link` per line).

CLI alternatives: copy files to `songs/` then `python import_songs.py` and `python init_db.py`.
Demo audio: `python generate_demo_audio.py` (`--minutes 3 --force` for longer synthetic tracks).

## Files
app.py, init_db.py, import_songs.py, generate_demo_audio.py, music.csv, cypher_queries.cypher,
core/ (config, db, auth, library, catalog, recommender, actions, player, ui, graph_view, views).
