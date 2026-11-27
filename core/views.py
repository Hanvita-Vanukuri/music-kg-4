"""All pages: login, sidebar, now-playing, Home, Search, Browse, Liked, Playlists, Recent, Recs, Graph, Profile."""
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from . import actions, auth, catalog, graph_view, library, player, recommender, ui
from .config import SONGS_DIR

NAV = [("Home", "🏠"), ("Search", "🔎"), ("Browse", "🧭"), ("Liked Songs", "💚"), ("Playlists", "📚"),
       ("Recently Played", "🕘"), ("Recommendations", "✨"), ("Knowledge Graph", "🕸️"), ("Add Songs", "➕"), ("Profile", "👤")]


# ------------------------------------------------------------------ auth
def login_page():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<div style="text-align:center;margin-top:5vh"><div class="brand" style="font-size:2.6rem">'
                    '🎧 Music<span>Graph</span></div><div class="muted">Discover music through a knowledge graph.'
                    '</div></div>', unsafe_allow_html=True)
        tab_in, tab_up = st.tabs(["Log in", "Sign up"])
        with tab_in:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                go = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if go:
                user = auth.login(u, p)
                if user:
                    token = auth.create_session(user["username"])
                    st.session_state.user, st.session_state.token = user, token
                    st.query_params["sid"] = token
                    actions.load_user_state()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with tab_up:
            with st.form("signup_form"):
                u = st.text_input("Choose a username", help="3-20 chars: a-z, 0-9, _")
                d = st.text_input("Display name")
                p = st.text_input("Password (min 6 chars)", type="password")
                go = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if go:
                ok, msg = auth.signup(u, d, p)
                (st.success if ok else st.error)(msg)


def sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown('<div class="brand">🎧 Music<span>Graph</span></div>', unsafe_allow_html=True)
        for name, icon in NAV:
            st.button(f"{icon}  {name}", key=f"nav_{name}", use_container_width=True,
                      type="primary" if st.session_state.page == name else "secondary",
                      on_click=actions.set_page, args=(name,))
        st.divider()
        st.markdown(f'<div class="userchip"><div class="avatar">{escape(user["display_name"][:1].upper())}</div>'
                    f'<div><b>{escape(user["display_name"])}</b><br><span class="cs">@{escape(user["username"])}'
                    f'</span></div></div>', unsafe_allow_html=True)
        st.button("Log out", key="logout", use_container_width=True, on_click=actions.logout)


# ------------------------------------------------------------------ now playing
def now_playing():
    sid = st.session_state.current
    if not sid:
        return
    s = recommender.get_song(sid)
    user = actions.username()
    recs = recommender.recommend(user, sid, k=6)
    q, qi = st.session_state.queue, st.session_state.qi
    up_next = recommender.get_song(q[qi + 1]) if 0 <= qi + 1 < len(q) else None
    with st.container(key="nowplaying"):
        c1, c2 = st.columns([1, 3.2], vertical_alignment="center")
        c1.markdown(ui.art_html(s["album"], radius=14), unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="np-label">NOW PLAYING</div><div class="np-title">{escape(s["title"])}</div>'
                f'<div class="muted">{escape(s["artist"])} · {escape(s["album"])}</div>'
                f'<div style="margin-top:6px"><span class="chip">{escape(s["genre"])}</span>'
                f'<span class="chip">{escape(s["mood"])}</span><span class="chip">{escape(s["language"])}</span>'
                f'<span class="chip">⚡ {s["energy"]:.0%}</span><span class="chip">💃 {s["danceability"]:.0%}</span>'
                f'<span class="chip">♩ {s["tempo"]:.0f} BPM</span></div>', unsafe_allow_html=True)
            player.render_player(s)
            b = st.columns([1, 1, 1, 1, 3])
            b[0].button("⏮ Prev", key="btn_prev", on_click=actions.prev_song, use_container_width=True,
                        disabled=qi <= 0)
            b[1].button("Next ⏭", key="btn_next", on_click=actions.next_song, use_container_width=True,
                        type="primary")
            liked = sid in st.session_state.liked
            b[2].button("♥ Liked" if liked else "♡ Like", key="np_like", on_click=actions.toggle_like,
                        args=(sid,), use_container_width=True)
            if b[3].button("＋ Playlist", key="np_add", use_container_width=True):
                ui.add_dialog(sid)
            if up_next:
                b[4].markdown(f"<div class='cs' style='padding-top:8px'>Up next: <b>{escape(up_next['title'])}"
                              f"</b> · {escape(up_next['artist'])}</div>", unsafe_allow_html=True)
    ui.section("Recommended based on this song",
               "Auto-generated from artist, genre, mood, language, energy, danceability, popularity, graph links "
               "and your listening history")
    ui.grid(recs, "np", cols=6)
    st.divider()


# ------------------------------------------------------------------ pages
def home_page():
    user = st.session_state.user
    hr = datetime.now().hour
    greet = "Good morning" if hr < 12 else "Good afternoon" if hr < 18 else "Good evening"
    st.markdown(f'<div class="hero"><h1>{greet}, {escape(user["display_name"])}</h1>'
                f'<div class="muted">Pick any song — recommendations appear automatically.</div></div>',
                unsafe_allow_html=True)
    ui.section("Made for you", "Your taste profile blended with what's popular")
    ui.grid(recommender.recommend(user["username"], None, k=6), "home_mfy", cols=6)
    recent = library.recent_plays(user["username"], 12)
    if recent:
        last = recommender.get_song(recent[0]["song_id"])
        ui.section(f"Because you played {last['title']}")
        ui.grid(recommender.recommend(user["username"], last["song_id"], k=6), "home_bp", cols=6)
    ui.section("Trending now")
    ui.grid(recommender.trending(6), "home_tr", cols=6, reasons=False)
    if recent:
        ui.section("Jump back in")
        ui.grid(recommender.songs_by_ids([r["song_id"] for r in recent[:6]]), "home_rp", cols=6, reasons=False)


def search_page():
    df = recommender.get_songs()
    ui.section("Search")
    q = st.text_input("Search", placeholder="Songs, artists, albums, genres, moods…",
                      label_visibility="collapsed", key="search_q")
    f1, f2, f3 = st.columns(3)
    genres = f1.multiselect("Genre", sorted(df["genre"].unique()))
    moods = f2.multiselect("Mood", sorted(df["mood"].unique()))
    langs = f3.multiselect("Language", sorted(df["language"].unique()))
    res = df
    if genres:
        res = res[res["genre"].isin(genres)]
    if moods:
        res = res[res["mood"].isin(moods)]
    if langs:
        res = res[res["language"].isin(langs)]
    if q.strip():
        hay = (res["title"] + " " + res["artist"] + " " + res["album"] + " " + res["genre"] + " "
               + res["mood"] + " " + res["language"]).str.lower()
        for tok in q.lower().split():
            res = res[hay.loc[res.index].str.contains(tok, regex=False)]
    res = res.sort_values("popularity", ascending=False)
    st.caption(f"{len(res)} result(s)" if (q.strip() or genres or moods or langs) else "Top songs")
    if res.empty:
        st.info("No songs matched. Try a different search.")
    for _, s in res.head(40).iterrows():
        ui.song_row(s.to_dict(), "search")


def _tile_colors(name):
    c1, c2 = ui._colors(name)
    return f"linear-gradient(135deg,{c1},{c2})"


def browse_page():
    df = recommender.get_songs()
    ui.section("Browse all")
    kind = st.radio("Browse by", ["Genre", "Mood", "Language"], horizontal=True, label_visibility="collapsed")
    col = kind.lower()
    counts = df[col].value_counts()
    for i in range(0, len(counts), 6):
        for c, (name, n) in zip(st.columns(6), list(counts.items())[i:i + 6]):
            c.markdown(f'<div class="tile" style="background:{_tile_colors(name)}">{escape(name)}'
                       f'<small>{n} song{"s" if n != 1 else ""}</small></div>', unsafe_allow_html=True)
    choice = st.selectbox(f"Open a {kind.lower()}", list(counts.index))
    ui.section(choice)
    ui.grid(df[df[col] == choice].sort_values("popularity", ascending=False).head(24), f"br_{col}", cols=6,
            reasons=False)


def liked_page():
    ids = library.liked_ids(actions.username())
    ui.section("Liked Songs", f"{len(ids)} song(s)")
    if not ids:
        st.info("Tap ♡ on any song to save it here. Liked songs also sharpen your recommendations.")
        return
    st.button("▶ Play all", type="primary", on_click=actions.play_queue, args=(ids,), key="liked_playall")
    for _, s in recommender.songs_by_ids(ids).iterrows():
        ui.song_row(s.to_dict(), "liked")


def playlists_page():
    user = actions.username()
    ui.section("Your Playlists")
    with st.form("new_playlist", clear_on_submit=True):
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        name = c1.text_input("New playlist name", placeholder="Gym · Focus · Late night drive")
        if c2.form_submit_button("Create", type="primary", use_container_width=True) and name.strip():
            library.create_playlist(user, name)
            st.rerun()
    pls = library.list_playlists(user)
    if not pls:
        st.info("No playlists yet. Create one above, or use ＋ on any song.")
        return
    options = {f"{p['name']}  ({p['n']} songs)": p["pid"] for p in pls}
    pid = options[st.selectbox("Open playlist", list(options))]
    ids = library.playlist_song_ids(user, pid)
    b1, b2, _ = st.columns([1, 1, 4])
    b1.button("▶ Play all", type="primary", on_click=actions.play_queue, args=(ids,), disabled=not ids,
              key="pl_playall", use_container_width=True)
    if b2.button("🗑 Delete playlist", key="pl_delete", use_container_width=True):
        library.delete_playlist(user, pid)
        st.rerun()
    if not ids:
        st.caption("This playlist is empty.")
    for _, s in recommender.songs_by_ids(ids).iterrows():
        ui.song_row(s.to_dict(), f"pl_{pid}", extra=("✕", library.remove_from_playlist, (user, pid, s["song_id"])))


def recent_page():
    recent = library.recent_plays(actions.username(), 40)
    ui.section("Recently Played")
    if not recent:
        st.info("Nothing yet — play a song!")
        return
    meta = {r["song_id"]: r for r in recent}
    for _, s in recommender.songs_by_ids([r["song_id"] for r in recent]).iterrows():
        m = meta[s["song_id"]]
        ui.song_row(s.to_dict(), "recent", note=f"{m['n']}× · {m['last_played'][:16].replace('T', ' ')} UTC")


def recs_page():
    user = actions.username()
    ui.section("Recommendations", "Multi-factor: graph relations + audio similarity + your likes + listening history")
    if st.session_state.current:
        s = recommender.get_song(st.session_state.current)
        ui.section(f"Because you're listening to {s['title']}")
        ui.grid(recommender.recommend(user, s["song_id"], k=12), "rc_cur", cols=6)
    liked = library.liked_ids(user)
    if liked:
        s = recommender.get_song(liked[0])
        ui.section(f"Because you liked {s['title']}")
        ui.grid(recommender.recommend(user, s["song_id"], k=6), "rc_like", cols=6)
    ui.section("Your taste profile", "Weighted by likes (×3) and recent plays")
    ui.grid(recommender.recommend(user, None, k=12), "rc_taste", cols=6)
    ui.section("Discover new artists", "Artists you haven't listened to yet")
    ui.grid(recommender.recommend(user, None, k=6, novel_artists_only=True), "rc_new", cols=6)
    with st.expander("How recommendations are scored"):
        st.markdown(
            "- **22%** audio similarity (energy, danceability, popularity, tempo)\n"
            "- **22%** metadata match (artist 40 / genre 25 / mood 20 / language 15)\n"
            "- **20%** Neo4j graph overlap (shared artist, album, genre, mood, language nodes)\n"
            "- **10%** collaborative signal (other users who liked/played the same song)\n"
            "- **20%** your taste profile (likes ×3 + recency-weighted plays)\n"
            "- **6%** popularity · recently played songs are demoted · max 3 songs per artist")


def graph_page():
    df = recommender.get_songs()
    ui.section("Knowledge Graph", "Artist → Song → Album → Genre → Mood, straight from Neo4j")
    modes = ["Now playing + recommendations", "Artist", "Genre", "Mood", "Language", "Most popular"]
    c1, c2, c3 = st.columns([2, 2, 1.2], vertical_alignment="bottom")
    mode = c1.selectbox("View", modes)
    ids = []
    if mode == modes[0]:
        cur = st.session_state.current
        if cur:
            ids = [cur] + recommender.recommend(actions.username(), cur, k=10)["song_id"].tolist()
        else:
            c2.info("Play a song first.")
    elif mode == "Most popular":
        ids = recommender.trending(30)["song_id"].tolist()
    else:
        col = mode.lower()
        val = c2.selectbox(mode, sorted(df[col].unique()))
        ids = df[df[col] == val].sort_values("popularity", ascending=False).head(40)["song_id"].tolist()
    show_lang = c3.toggle("Languages", value=False)
    if not ids:
        return
    html, n_nodes, n_edges, cypher = graph_view.build(ids, show_lang)
    st.markdown("".join(
        f'<span class="chip" style="border:1px solid {c}">● {t}</span>' for t, (c, _, _) in graph_view.STYLE.items()
        if show_lang or t != "Language"), unsafe_allow_html=True)
    st.caption(f"{n_nodes} nodes · {n_edges} relationships · drag, zoom and hover nodes")
    components.html(html, height=670)
    with st.expander("Cypher behind this view"):
        st.code(cypher, language="cypher")


def _pick(label, options, key):
    """Dropdown of existing values plus a 'New…' option."""
    choice = st.selectbox(label, sorted(options) + ["➕ New…"], key=f"{key}_sel")
    if choice == "➕ New…":
        return st.text_input(f"New {label.lower()}", key=f"{key}_new").strip()
    return choice


def add_songs_page():
    df = recommender.get_songs()
    ui.section("Add songs", "Upload full-length audio or attach Spotify links, no terminal needed")
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)
    local = int(df["audio_file"].map(lambda f: bool(f) and (SONGS_DIR / Path(f).name).is_file()).sum())
    m = st.columns(3)
    m[0].metric("Songs", len(df))
    m[1].metric("With local audio", local)
    m[2].metric("With Spotify link", int((df["spotify_id"] != "").sum()))
    tab_up, tab_sp = st.tabs(["Upload / add a song", "Attach Spotify links"])

    with tab_up:
        n = st.session_state.setdefault("add_n", 0)
        k = lambda x: f"add_{x}_{n}"  # noqa: E731  (new keys after each save = cleared form)
        up = st.file_uploader("Audio file (full-length mp3, wav, m4a, ogg, flac)",
                              type=[e[1:] for e in sorted(catalog.AUDIO_EXTS)], key=k("file"))
        c1, c2 = st.columns(2)
        title = c1.text_input("Song title", key=k("title"))
        artist = c2.text_input("Artist", key=k("artist"))
        album = c1.text_input("Album", placeholder="Single", key=k("album"))
        with c2:
            genre = _pick("Genre", df["genre"].unique(), k("genre"))
        c3, c4 = st.columns(2)
        with c3:
            mood = _pick("Mood", df["mood"].unique(), k("mood"))
        with c4:
            lang = _pick("Language", df["language"].unique(), k("lang"))
        link = st.text_input("Spotify link (optional, plays the full song through Spotify)", key=k("link"))
        s1, s2, s3, s4 = st.columns(4)
        energy = s1.slider("Energy", 0.0, 1.0, 0.5, 0.05, key=k("en"))
        dance = s2.slider("Danceability", 0.0, 1.0, 0.5, 0.05, key=k("da"))
        pop = s3.slider("Popularity", 0, 100, 50, key=k("po"))
        tempo = s4.slider("Tempo (BPM)", 40, 220, 100, key=k("te"))
        if st.button("Add song", type="primary", key=k("go")):
            try:
                audio = (up.name, up.getvalue()) if up else None
                catalog.add_song({"song": title, "artist": artist, "album": album, "genre": genre, "mood": mood,
                                  "language": lang, "energy": energy, "danceability": dance, "popularity": pop,
                                  "tempo": tempo, "spotify_id": link}, audio)
                recommender.refresh()
                st.session_state.flash = f"Added “{title}” by {artist}. Search for it and press ▶."
                st.session_state.add_n = n + 1
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with tab_sp:
        opts = {f"{r.title} — {r.artist}": r.song_id for r in df.itertuples()}
        choice = st.selectbox("Song", list(opts), key="sp_song")
        sid = opts[choice]
        s = recommender.get_song(sid)
        a, b = st.columns([1, 3], vertical_alignment="bottom")
        a.link_button("🔍 Find on Spotify", "https://open.spotify.com/search/" + quote(f"{s['title']} {s['artist']}"))
        b.caption("Open the song on Spotify → ⋯ → Share → Copy Song Link, then paste it below.")
        link = st.text_input("Spotify link", value="", key=f"sp_link_{sid}",
                             placeholder="https://open.spotify.com/track/…")
        st.caption("Current: " + (f"track `{s['spotify_id']}`" if s["spotify_id"] else "none"))
        if st.button("Save link", type="primary", key="sp_save"):
            try:
                catalog.set_spotify(sid, link)
                recommender.refresh()
                st.session_state.flash = f"Saved Spotify link for “{s['title']}”."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        with st.expander("Bulk add: one per line as  Song title | Spotify link"):
            text = st.text_area("Lines", height=160, key="sp_bulk", label_visibility="collapsed",
                                placeholder="Blinding Lights | https://open.spotify.com/track/...\nShape of You | https://open.spotify.com/track/...")
            if st.button("Save all", key="sp_bulk_go"):
                ok, missed = catalog.bulk_set_spotify(text, df)
                recommender.refresh()
                st.success(f"Updated {ok} song(s).")
                if missed:
                    st.warning("No match / invalid link for: " + ", ".join(missed))


def profile_page():
    user = st.session_state.user
    uname = user["username"]
    ui.section(f"{user['display_name']}", f"@{uname}")
    stt = library.user_stats(uname)
    m = st.columns(4)
    m[0].metric("Liked songs", stt["likes"])
    m[1].metric("Total plays", stt["plays"])
    m[2].metric("Playlists", stt["playlists"])
    m[3].metric("Member since", (stt["joined"] or "")[:10])
    g, a = st.columns(2)
    with g:
        st.markdown("**Top genres**")
        data = library.top_genres(uname)
        if data:
            st.bar_chart(pd.DataFrame({"plays": [d["n"] for d in data]}, index=[d["name"] for d in data]), color="#1DB954")
        else:
            st.caption("Play some songs to see stats.")
    with a:
        st.markdown("**Top artists**")
        data = library.top_artists(uname)
        if data:
            st.bar_chart(pd.DataFrame({"plays": [d["n"] for d in data]}, index=[d["name"] for d in data]), color="#1DB954")
    st.divider()
    c1, c2 = st.columns(2)
    with c1.form("name_form"):
        st.markdown("**Edit profile**")
        nm = st.text_input("Display name", value=user["display_name"])
        if st.form_submit_button("Save", type="primary") and nm.strip():
            auth.update_display_name(uname, nm)
            st.session_state.user["display_name"] = nm.strip()
            st.rerun()
    with c2.form("pw_form", clear_on_submit=True):
        st.markdown("**Change password**")
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        if st.form_submit_button("Update password"):
            ok, msg = auth.change_password(uname, old, new)
            (st.success if ok else st.error)(msg)


PAGES = {"Home": home_page, "Search": search_page, "Browse": browse_page, "Liked Songs": liked_page,
         "Playlists": playlists_page, "Recently Played": recent_page, "Recommendations": recs_page,
         "Knowledge Graph": graph_page, "Add Songs": add_songs_page, "Profile": profile_page}


def render_page():
    now_playing()
    PAGES.get(st.session_state.page, home_page)()
