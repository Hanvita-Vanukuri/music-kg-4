"""Signup / login / session tokens. Passwords: PBKDF2-HMAC-SHA256 + per-user salt."""
import hashlib
import hmac
import re
import secrets

import streamlit as st

from . import db
from .config import SESSION_DAYS

_ITER = 200_000


def _hash(password, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _ITER).hex()


def signup(username, display_name, password):
    username = (username or "").strip().lower()
    display_name = (display_name or "").strip() or username
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
        return False, "Username must be 3-20 characters: letters, numbers, underscore."
    if len(password or "") < 6:
        return False, "Password must be at least 6 characters."
    if db.run("MATCH (u:User {username:$u}) RETURN u.username AS u", u=username):
        return False, "That username is already taken."
    salt = secrets.token_hex(16)
    db.run(
        "CREATE (u:User {username:$u, display_name:$d, salt:$s, password_hash:$h, created_at:datetime()})",
        u=username, d=display_name, s=salt, h=_hash(password, salt),
    )
    return True, "Account created. You can log in now."


def login(username, password):
    username = (username or "").strip().lower()
    rows = db.run(
        "MATCH (u:User {username:$u}) RETURN u.username AS username, u.display_name AS display_name, "
        "u.salt AS salt, u.password_hash AS h",
        u=username,
    )
    if not rows:
        return None
    r = rows[0]
    if hmac.compare_digest(_hash(password or "", r["salt"]), r["h"]):
        return {"username": r["username"], "display_name": r["display_name"]}
    return None


def create_session(username):
    db.run("MATCH (s:Session) WHERE s.expires_at < datetime() DETACH DELETE s")
    token = secrets.token_urlsafe(32)
    db.run(
        "MATCH (u:User {username:$u}) "
        "CREATE (s:Session {token:$t, expires_at: datetime() + duration({days:$d})})-[:OF_USER]->(u)",
        u=username, t=token, d=SESSION_DAYS,
    )
    return token


def user_from_token(token):
    if not token:
        return None
    rows = db.run(
        "MATCH (s:Session {token:$t})-[:OF_USER]->(u:User) WHERE s.expires_at > datetime() "
        "RETURN u.username AS username, u.display_name AS display_name",
        t=token,
    )
    return rows[0] if rows else None


def logout(token):
    if token:
        db.run("MATCH (s:Session {token:$t}) DETACH DELETE s", t=token)


def update_display_name(username, display_name):
    db.run("MATCH (u:User {username:$u}) SET u.display_name=$d", u=username, d=display_name.strip())


def change_password(username, old, new):
    if len(new or "") < 6:
        return False, "New password must be at least 6 characters."
    if not login(username, old):
        return False, "Current password is incorrect."
    salt = secrets.token_hex(16)
    db.run("MATCH (u:User {username:$u}) SET u.salt=$s, u.password_hash=$h", u=username, s=salt, h=_hash(new, salt))
    return True, "Password updated."


def restore_session():
    """Called on every run: re-hydrate st.session_state.user from the ?sid= token."""
    if st.session_state.get("user"):
        return
    token = st.query_params.get("sid")
    user = user_from_token(token) if token else None
    if user:
        st.session_state.user = user
        st.session_state.token = token
