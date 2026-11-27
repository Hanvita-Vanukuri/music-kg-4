import streamlit as st

st.set_page_config(page_title="MusicGraph", page_icon="🎧", layout="wide", initial_sidebar_state="expanded")

from core import actions, auth, db, ui, views  # noqa: E402

ui.inject_css()
actions.init_state()

try:
    db.get_driver()
except Exception as exc:  # Neo4j not running / wrong credentials
    st.error("Cannot connect to Neo4j. Start it (`docker compose up -d`), check `.env`, "
             "then run `python init_db.py`.")
    st.code(str(exc))
    st.stop()

auth.restore_session()
if st.session_state.user is None:
    views.login_page()
    st.stop()

if not st.session_state.liked and "liked_loaded" not in st.session_state:
    actions.load_user_state()
    st.session_state.liked_loaded = True

views.sidebar()
views.render_page()
