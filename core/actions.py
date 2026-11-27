"""Session state + callbacks (play queue, likes, navigation, logout)."""
import streamlit as st

from . import auth, library, recommender

QUEUE_LEN = 15


def init_state():
    defaults = {"user": None, "token": None, "page": "Home", "queue": [], "qi": -1,
                "current": None, "liked": set(), "version": 0}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def username():
    return st.session_state.user["username"]


def load_user_state():
    st.session_state.liked = set(library.liked_ids(username()))


def set_page(name):
    st.session_state.page = name


def _start(song_id):
    """Make song_id the current track and log it as a play (feeds future recommendations)."""
    st.session_state.current = song_id
    library.record_play(username(), song_id)
    st.session_state.version += 1


def play_song(song_id):
    """Play a song; the up-next queue is auto-built from graph + similarity + taste recommendations."""
    recs = recommender.recommend(username(), song_id, k=QUEUE_LEN)
    st.session_state.queue = [song_id] + recs["song_id"].tolist()
    st.session_state.qi = 0
    _start(song_id)


def play_queue(song_ids):
    if not song_ids:
        return
    st.session_state.queue = list(song_ids)
    st.session_state.qi = 0
    _start(song_ids[0])


def next_song():
    q, i = st.session_state.queue, st.session_state.qi
    if not st.session_state.current:
        return
    if i + 1 >= len(q):  # queue exhausted -> rebuild from the current song
        cur = st.session_state.current
        recs = recommender.recommend(username(), cur, k=QUEUE_LEN)
        q = [cur] + recs["song_id"].tolist()
        st.session_state.queue, i = q, 0
        if len(q) == 1:
            return
    st.session_state.qi = i + 1
    _start(q[i + 1])


def prev_song():
    q, i = st.session_state.queue, st.session_state.qi
    if i > 0:
        st.session_state.qi = i - 1
        _start(q[i - 1])


def toggle_like(song_id):
    liked = st.session_state.liked
    if song_id in liked:
        library.unlike(username(), song_id)
        liked.discard(song_id)
        st.toast("Removed from Liked Songs")
    else:
        library.like(username(), song_id)
        liked.add(song_id)
        st.toast("Added to Liked Songs 💚")
    st.session_state.version += 1


def logout():
    auth.logout(st.session_state.get("token"))
    for k in ("user", "token", "queue", "qi", "current", "liked", "liked_loaded"):
        st.session_state.pop(k, None)
    st.query_params.clear()
