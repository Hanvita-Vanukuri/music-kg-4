import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "musicgraph123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CSV_PATH = BASE_DIR / "music.csv"
SONGS_DIR = BASE_DIR / "songs"
SESSION_DAYS = 7
