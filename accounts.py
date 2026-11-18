"""Local username and password records. Case data is never stored here."""
from contextlib import closing
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3


ACCOUNT_DB = Path(__file__).with_name('.accounts') / 'users.sqlite3'
USERNAME = re.compile(r'[A-Za-z0-9_.-]{3,32}\Z')


def credentials(payload, creating):
    username = payload.get('username')
    password = payload.get('password')
    if not isinstance(username, str) or not USERNAME.fullmatch(username.strip()):
        return None
    if not isinstance(password, str) or not (15 if creating else 1) <= len(password) <= 128:
        return None
    return username.strip().lower(), password


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**15, r=8, p=3,
                          maxmem=64 * 1024 * 1024, dklen=32)


def connect():
    ACCOUNT_DB.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    conn = sqlite3.connect(ACCOUNT_DB, timeout=3)
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL
        )''')
        return conn
    except Exception:
        conn.close()
        raise


def register(username, password):
    salt = secrets.token_bytes(16)
    digest = password_hash(password, salt)
    with closing(connect()) as conn, conn:
        inserted = conn.execute(
            'INSERT OR IGNORE INTO users (username, salt, password_hash) VALUES (?, ?, ?)',
            (username, salt, digest),
        )
        return inserted.rowcount == 1


def authenticate(username, password):
    with closing(connect()) as conn:
        row = conn.execute('SELECT salt, password_hash FROM users WHERE username = ?', (username,)).fetchone()
    salt, expected = row if row is not None else (bytes(16), bytes(32))
    matches = hmac.compare_digest(password_hash(password, salt), expected)
    return row is not None and matches
