# -*- coding: utf-8 -*-
"""
scan_library.py
Scans FLAC_MUSIC_DIR (default: ~/Music), extracts FLAC metadata via mutagen,
and writes the local catalogue into flac_library.db (SQLite).
Run once; re-running is safe (REPLACE INTO upserts data).
"""

import os, sqlite3, random, sys
from pathlib import Path
from mutagen.flac import FLAC
from mutagen import MutagenError

MUSIC_DIR = os.environ.get("FLAC_MUSIC_DIR", str(Path.home() / "Music"))
DB_PATH   = os.path.join(os.path.dirname(__file__), "flac_library.db")

GENRE_FALLBACK = [
    "Rock", "Pop", "Jazz", "Classical", "Electronic",
    "Hip-Hop", "Country", "Blues", "R&B", "Metal",
    "Folk", "Indie", "Ambient", "Soul", "Reggae"
]

# ── helpers ───────────────────────────────────────────────────────────────────

def tag(f, key, default=None):
    """Return first value of a FLAC tag, or default."""
    try:
        val = f.tags.get(key)
        if val:
            return val[0].strip() or default
    except Exception:
        pass
    return default

def safe_int(v, default=None):
    try:
        return int(str(v).split("/")[0].strip())
    except (TypeError, ValueError):
        return default

def safe_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def human_bitrate(bps):
    """Convert bits-per-second to kbps string."""
    return f"{round(bps / 1000)} kbps" if bps else "Unknown"

# ── schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS Artists (
    artist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Genres (
    genre_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Albums (
    album_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id    INTEGER NOT NULL REFERENCES Artists(artist_id),
    title        TEXT NOT NULL,
    release_year INTEGER,
    UNIQUE(artist_id, title)
);

CREATE TABLE IF NOT EXISTS AudioQuality (
    quality_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_format TEXT DEFAULT 'FLAC',
    bit_depth   INTEGER,
    sample_rate INTEGER,
    bitrate     TEXT,
    UNIQUE(bit_depth, sample_rate, bitrate)
);

CREATE TABLE IF NOT EXISTS Songs (
    song_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    album_id     INTEGER NOT NULL REFERENCES Albums(album_id),
    genre_id     INTEGER REFERENCES Genres(genre_id),
    quality_id   INTEGER REFERENCES AudioQuality(quality_id),
    track_number INTEGER,
    duration     REAL,
    file_size    INTEGER,
    play_count   INTEGER DEFAULT 0,
    rating       REAL,
    file_path    TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS Playlists (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS PlaylistSongs (
    playlist_id INTEGER REFERENCES Playlists(playlist_id),
    song_id     INTEGER REFERENCES Songs(song_id),
    PRIMARY KEY (playlist_id, song_id)
);
"""

# ── main ──────────────────────────────────────────────────────────────────────

def get_or_insert(cur, table, col, val):
    """Return id of existing row, or insert and return new id."""
    cur.execute(f"SELECT rowid FROM {table} WHERE {col}=?", (val,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(f"INSERT INTO {table} ({col}) VALUES (?)", (val,))
    return cur.lastrowid

def main():
    print(f"[scan_library] Scanning {MUSIC_DIR} ...")
    flac_files = list(Path(MUSIC_DIR).rglob("*.flac"))
    total = len(flac_files)
    print(f"[scan_library] Found {total} FLAC files.")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA)
    con.commit()

    ok = skipped = errors = 0

    for i, path in enumerate(flac_files, 1):
        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}]  ok={ok}  skip={skipped}  err={errors}", flush=True)
        try:
            audio = FLAC(str(path))
        except MutagenError as e:
            errors += 1
            print(f"  SKIP (mutagen): {path.name} — {e}", file=sys.stderr)
            continue

        t = audio.tags or {}

        # ── core tags ──────────────────────────────────────────────────────────
        title       = tag(audio, "title")        or path.stem
        artist_name = (tag(audio, "albumartist")
                    or tag(audio, "artist")
                    or path.parts[-3] if len(path.parts) >= 3 else "Unknown Artist")
        album_title = tag(audio, "album")        or path.parent.name
        year_raw    = tag(audio, "date") or tag(audio, "originaldate") or tag(audio, "originalyear")
        year        = safe_int(str(year_raw)[:4]) if year_raw else None
        genre_name  = tag(audio, "genre")
        track_num   = safe_int(tag(audio, "tracknumber"))
        duration    = round(audio.info.length, 3)
        file_size   = path.stat().st_size
        bit_depth   = audio.info.bits_per_sample
        sample_rate = audio.info.sample_rate
        bitrate_str = human_bitrate(getattr(audio.info, "bitrate", None))

        # ── random fill for missing ────────────────────────────────────────────
        if not genre_name:
            genre_name = random.choice(GENRE_FALLBACK) if random.random() > 0.15 else None
        play_count = random.randint(0, 300)  if random.random() > 0.1 else 0
        rating     = round(random.uniform(2.5, 5.0), 1) if random.random() > 0.2 else None

        try:
            # Artists
            artist_id = get_or_insert(cur, "Artists", "name", artist_name)

            # Genres
            genre_id = None
            if genre_name:
                genre_id = get_or_insert(cur, "Genres", "name", genre_name)

            # Albums
            cur.execute(
                "SELECT album_id FROM Albums WHERE artist_id=? AND title=?",
                (artist_id, album_title)
            )
            row = cur.fetchone()
            if row:
                album_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO Albums (artist_id, title, release_year) VALUES (?,?,?)",
                    (artist_id, album_title, year)
                )
                album_id = cur.lastrowid

            # AudioQuality
            cur.execute(
                "SELECT quality_id FROM AudioQuality WHERE bit_depth=? AND sample_rate=? AND bitrate=?",
                (bit_depth, sample_rate, bitrate_str)
            )
            row = cur.fetchone()
            if row:
                quality_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO AudioQuality (file_format, bit_depth, sample_rate, bitrate) VALUES ('FLAC',?,?,?)",
                    (bit_depth, sample_rate, bitrate_str)
                )
                quality_id = cur.lastrowid

            # Songs — upsert on file_path
            cur.execute("""
                INSERT INTO Songs
                    (title, album_id, genre_id, quality_id, track_number,
                     duration, file_size, play_count, rating, file_path)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(file_path) DO UPDATE SET
                    title=excluded.title,
                    genre_id=excluded.genre_id,
                    quality_id=excluded.quality_id,
                    track_number=excluded.track_number,
                    duration=excluded.duration,
                    file_size=excluded.file_size
            """, (
                title, album_id, genre_id, quality_id, track_num,
                duration, file_size, play_count, rating, str(path)
            ))
            ok += 1

        except sqlite3.Error as e:
            errors += 1
            print(f"  DB ERR: {path.name} — {e}", file=sys.stderr)
            con.rollback()
            continue

        if i % 50 == 0:
            con.commit()

    con.commit()
    con.close()
    print(f"\n[scan_library] Done. {ok} imported, {skipped} skipped, {errors} errors.")
    print(f"[scan_library] Database: {DB_PATH}")

if __name__ == "__main__":
    main()
