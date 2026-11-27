"""Audio player: HTML5 <audio> + custom controls (play/pause, seek, volume) in a component.
Prev/Next are Streamlit buttons (keys btn_prev / btn_next); when a track ends the component
clicks btn_next to continue the queue."""
import base64
import json
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from .config import BASE_DIR, SONGS_DIR

INLINE_MAX = 2 * 1024 * 1024          # <= 2 MB: embed as base64; bigger: stream from /app/static
STATIC_EXT = {".mp3", ".wav", ".ogg"}  # extensions Streamlit static serving allows
STATIC_DIR = BASE_DIR / "static" / "songs"

_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
         ".flac": "audio/flac", ".aac": "audio/aac"}

TEMPLATE = """
<style>
 body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:#b3b3b3;background:transparent}
 .p{display:flex;align-items:center;gap:12px;background:#181818;border:1px solid #2a2a2a;border-radius:12px;padding:12px 16px}
 #pp{width:46px;height:46px;border-radius:50%;border:none;background:#1DB954;color:#000;font-size:18px;cursor:pointer;transition:.15s}
 #pp:hover{transform:scale(1.08);background:#1ed760}
 input[type=range]{accent-color:#1DB954;cursor:pointer;height:4px}
 #seek{flex:1;min-width:60px} #vol{width:90px} span{font-size:12px;min-width:34px;text-align:center}
</style>
<div class="p">
 <button id="pp" title="Play / Pause">&#9208;</button>
 <span id="cur">0:00</span>
 <input id="seek" type="range" min="0" max="1000" value="0">
 <span id="dur">0:00</span>
 <span style="min-width:0">&#128266;</span>
 <input id="vol" type="range" min="0" max="100" value="80">
</div>
<audio id="a" preload="auto"></audio>
<script>
const a=document.getElementById('a'),pp=document.getElementById('pp'),seek=document.getElementById('seek'),
      vol=document.getElementById('vol'),cur=document.getElementById('cur'),dur=document.getElementById('dur');
let v=0.8; try{v=parseFloat(window.parent.sessionStorage.getItem('mkg_vol')||'0.8')}catch(e){}
a.src=__SRC__;
a.volume=v; vol.value=v*100;
const fmt=t=>{if(!isFinite(t))return'0:00';const m=Math.floor(t/60),s=Math.floor(t%60);return m+':'+String(s).padStart(2,'0')};
a.addEventListener('loadedmetadata',()=>dur.textContent=fmt(a.duration));
a.addEventListener('timeupdate',()=>{if(a.duration)seek.value=a.currentTime/a.duration*1000;cur.textContent=fmt(a.currentTime)});
a.addEventListener('play',()=>pp.innerHTML='&#9208;');
a.addEventListener('pause',()=>pp.innerHTML='&#9654;');
pp.onclick=()=>a.paused?a.play():a.pause();
seek.oninput=()=>{if(a.duration)a.currentTime=seek.value/1000*a.duration};
vol.oninput=()=>{a.volume=vol.value/100;try{window.parent.sessionStorage.setItem('mkg_vol',a.volume)}catch(e){}};
a.addEventListener('ended',()=>{try{const b=window.parent.document.querySelector('.st-key-btn_next button');if(b)b.click();}catch(e){}});
a.play().catch(()=>{pp.innerHTML='&#9654;'});
</script>
"""


@st.cache_data(show_spinner=False, max_entries=8)
def _inline_src(filename):
    path = SONGS_DIR / Path(filename).name
    mime = _MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return json.dumps(f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode())


def _static_src(path):
    """Copy to ./static/songs (served by Streamlit at /app/static/songs/...) and return a JS expression."""
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    dest = STATIC_DIR / path.name
    if not dest.exists() or dest.stat().st_size != path.stat().st_size:
        shutil.copy2(path, dest)
    return "window.parent.location.origin + " + json.dumps("/app/static/songs/" + quote(path.name))


def render_player(song):
    spid = (song.get("spotify_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{22}", spid):
        spid = ""
    filename = song.get("audio_file", "")
    path = SONGS_DIR / Path(filename).name if filename else None  # no path traversal
    local_ok = bool(path and path.is_file())

    use_spotify = bool(spid) and not local_ok
    if spid and local_ok:  # both available: let the user choose
        use_spotify = st.radio("Source", ["Spotify", "Local file"], horizontal=True, key="player_src",
                               label_visibility="collapsed") == "Spotify"
    if use_spotify:
        components.iframe(f"https://open.spotify.com/embed/track/{spid}?utm_source=generator&theme=0", height=152)
        st.caption("Spotify player: press play inside it. Logged in to Spotify in this browser = full track "
                   "(depends on your account); otherwise a preview. Use Prev/Next below to move through the queue.")
        return
    if not local_ok:
        st.info(f"No audio for this song. Add `{filename or 'your_file.mp3'}` to `songs/` or a Spotify link in "
                f"the `spotify_id` column of music.csv.")
        return
    big = path.stat().st_size > INLINE_MAX and path.suffix.lower() in STATIC_EXT
    src = _static_src(path) if big else _inline_src(filename)
    components.html(TEMPLATE.replace("__SRC__", src), height=84)
