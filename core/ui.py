"""CSS theme + reusable UI pieces (artwork, song cards, song rows, add-to-playlist dialog)."""
import hashlib
from html import escape

import streamlit as st

from . import actions, library, recommender

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"], .stApp {font-family:'Inter',-apple-system,'Segoe UI',sans-serif;}
.stApp {background:linear-gradient(180deg,#1a1a1a 0%,#121212 340px);}
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] {background:transparent;}
.block-container {padding-top:2rem; max-width:1500px;}
section[data-testid="stSidebar"] {background:#000; border-right:1px solid #1c1c1c;}
section[data-testid="stSidebar"] .stButton>button {background:transparent;border:none;color:#b3b3b3;
  justify-content:flex-start;text-align:left;font-weight:600;border-radius:8px;padding:.55rem .8rem;}
section[data-testid="stSidebar"] .stButton>button:hover {color:#fff;background:#1a1a1a;}
section[data-testid="stSidebar"] .stButton>button[kind="primary"] {background:#242424;color:#1DB954;}
.brand {font-size:1.7rem;font-weight:800;color:#fff;letter-spacing:-.5px;margin:.2rem 0 1rem;}
.brand span {color:#1DB954;}
.userchip {display:flex;gap:10px;align-items:center;padding:8px;border-radius:10px;background:#111;}
.avatar {width:36px;height:36px;border-radius:50%;background:#1DB954;color:#000;font-weight:800;
  display:flex;align-items:center;justify-content:center;}
.stButton>button {border-radius:500px;border:1px solid #333;background:#1f1f1f;color:#fff;font-weight:600;
  transition:all .15s ease;}
.stButton>button:hover {border-color:#1DB954;color:#1DB954;transform:scale(1.03);}
.stButton>button[kind="primary"] {background:#1DB954;color:#000;border:none;}
.stButton>button[kind="primary"]:hover {background:#1ed760;color:#000;}
[class*="st-key-card_"] {background:#181818;border-radius:12px;padding:12px;transition:all .25s ease;}
[class*="st-key-card_"]:hover {background:#2a2a2a;transform:translateY(-4px);box-shadow:0 10px 24px rgba(0,0,0,.5);}
[class*="st-key-row_"] {border-radius:8px;padding:4px 8px;transition:background .15s;}
[class*="st-key-row_"]:hover {background:#242424;}
.st-key-nowplaying {background:linear-gradient(135deg,#1db95426,#181818 55%);border-radius:16px;padding:18px;
  border:1px solid #262626;margin-bottom:8px;}
.art {aspect-ratio:1/1;width:100%;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.85);
  font-weight:800;font-size:1.8rem;box-shadow:0 6px 18px rgba(0,0,0,.45);}
.art-sm {width:48px;height:48px;aspect-ratio:auto;font-size:1rem;}
.ct {font-weight:700;color:#fff;margin-top:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cs {color:#a7a7a7;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cr {color:#1DB954;font-size:.75rem;margin:2px 0 6px;min-height:1.1rem;}
.section-title {font-size:1.5rem;font-weight:800;margin:1.6rem 0 .6rem;color:#fff;}
.muted {color:#a7a7a7;}
.hero {background:linear-gradient(135deg,#1DB95466,#121212);padding:28px 30px;border-radius:16px;margin-bottom:6px;}
.hero h1 {margin:0;font-size:2.2rem;font-weight:800;}
.chip {display:inline-block;padding:3px 12px;border-radius:50px;background:#2a2a2a;color:#ddd;font-size:.78rem;margin:2px 6px 2px 0;}
.np-label {font-size:.72rem;letter-spacing:.15em;color:#1DB954;font-weight:800;}
.np-title {font-size:2rem;font-weight:800;line-height:1.1;margin:2px 0;}
.tile {border-radius:12px;padding:18px 14px;height:92px;font-weight:800;color:#fff;font-size:1.05rem;
  box-shadow:0 4px 14px rgba(0,0,0,.4);margin-bottom:12px;}
.tile small {display:block;font-weight:400;opacity:.8;}
.playing {color:#1DB954 !important;}
@media (max-width: 720px) {.np-title{font-size:1.4rem}.block-container{padding:1rem .6rem}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def _colors(seed):
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    h1 = h % 360
    h2 = (h1 + 40 + (h >> 8) % 80) % 360
    return f"hsl({h1},62%,40%)", f"hsl({h2},70%,22%)"


def art_html(album, small=False, radius=10):
    c1, c2 = _colors(album)
    txt = escape("".join(w[0] for w in album.split()[:2]).upper() or "♪")
    cls = "art art-sm" if small else "art"
    return (f'<div class="{cls}" style="background:linear-gradient(135deg,{c1},{c2});border-radius:{radius}px">'
            f"{txt}</div>")


def section(title, subtitle=None):
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="muted" style="margin-top:-8px;margin-bottom:10px">{escape(subtitle)}</div>',
                    unsafe_allow_html=True)


@st.dialog("Add to playlist")
def add_dialog(song_id):
    user = actions.username()
    song = recommender.get_song(song_id)
    st.markdown(f"**{song['title']}** · {song['artist']}")
    playlists = library.list_playlists(user)
    if playlists:
        options = {f"{p['name']} ({p['n']})": p["pid"] for p in playlists}
        choice = st.selectbox("Choose a playlist", list(options))
        if st.button("Add to playlist", type="primary", key="dlg_add"):
            library.add_to_playlist(user, options[choice], song_id)
            st.toast("Added to playlist ✅")
            st.rerun()
        st.divider()
    new = st.text_input("Or create a new playlist", key="dlg_new", placeholder="My road trip mix")
    if st.button("Create & add", key="dlg_create"):
        if new.strip():
            pid = library.create_playlist(user, new)
            library.add_to_playlist(user, pid, song_id)
            st.toast("Playlist created ✅")
            st.rerun()
        else:
            st.warning("Give the playlist a name.")


def _buttons(sid, ctx, cols):
    liked = sid in st.session_state.liked
    cols[0].button("▶", key=f"{ctx}_play_{sid}", on_click=actions.play_song, args=(sid,),
                   type="primary", use_container_width=True, help="Play")
    cols[1].button("♥" if liked else "♡", key=f"{ctx}_like_{sid}", on_click=actions.toggle_like, args=(sid,),
                   use_container_width=True, help="Unlike" if liked else "Like")
    if cols[2].button("＋", key=f"{ctx}_add_{sid}", use_container_width=True, help="Add to playlist"):
        add_dialog(sid)


def song_card(s, ctx, reason=None):
    sid = s["song_id"]
    with st.container(key=f"card_{ctx}_{sid}"):
        sub = reason if reason else f"{s['genre']} · {s['mood']}"
        st.markdown(
            f"{art_html(s['album'])}<div class='ct'>{escape(s['title'])}</div>"
            f"<div class='cs'>{escape(s['artist'])}</div>"
            f"<div class='cr'>{escape(sub)}</div>", unsafe_allow_html=True)
        _buttons(sid, ctx, st.columns(3))


def song_row(s, ctx, extra=None, note=None):
    """One list row. extra = (label, callback, args) adds a 4th action button."""
    sid = s["song_id"]
    widths = [0.7, 3.4, 2.2, 2.2, 0.7, 0.7, 0.7] + ([0.8] if extra else [])
    with st.container(key=f"row_{ctx}_{sid}"):
        c = st.columns(widths, vertical_alignment="center")
        c[0].markdown(art_html(s["album"], small=True, radius=6), unsafe_allow_html=True)
        cls = "ct playing" if sid == st.session_state.current else "ct"
        c[1].markdown(f"<div class='{cls}' style='margin:0'>{escape(s['title'])}</div>"
                      f"<div class='cs'>{escape(s['artist'])}</div>", unsafe_allow_html=True)
        c[2].markdown(f"<div class='cs'>{escape(s['album'])}</div>", unsafe_allow_html=True)
        c[3].markdown(f"<div class='cs'>{escape(s['genre'])} · {escape(s['mood'])} · {escape(s['language'])}"
                      f"{'<br>' + escape(note) if note else ''}</div>", unsafe_allow_html=True)
        _buttons(sid, ctx, c[4:7])
        if extra:
            label, cb, args = extra
            c[7].button(label, key=f"{ctx}_x_{sid}", on_click=cb, args=args, use_container_width=True)


def grid(df, ctx, cols=6, reasons=True):
    rows = df.to_dict("records")
    for i in range(0, len(rows), cols):
        for col, s in zip(st.columns(cols), rows[i:i + cols]):
            with col:
                song_card(s, ctx, s.get("reason") if reasons else None)
