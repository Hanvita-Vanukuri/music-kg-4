"""Thin Neo4j access layer (no Streamlit dependency, so init_db.py can use it too)."""
from neo4j import GraphDatabase

from .config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        drv.verify_connectivity()  # raises if Neo4j is down / wrong credentials
        _driver = drv
    return _driver


def run(cypher, **params):
    """Run a Cypher query and return a list of plain dicts."""
    with get_driver().session(database=NEO4J_DATABASE) as session:
        return [record.data() for record in session.run(cypher, **params)]
