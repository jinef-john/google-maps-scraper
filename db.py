import json
import logging
import os
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_INIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -64000;

CREATE TABLE IF NOT EXISTS places (
    place_id            TEXT PRIMARY KEY,
    name                TEXT,
    address             TEXT,
    address_components  TEXT,
    plus_code           TEXT,
    lat                 REAL,
    lng                 REAL,
    rating              REAL,
    review_count        INTEGER,
    website             TEXT,
    phone               TEXT,
    email               TEXT,
    fax                 TEXT,
    price_level         TEXT,
    description         TEXT,
    categories          TEXT,
    primary_type        TEXT,
    hours               TEXT,
    photos              TEXT,
    about               TEXT,
    menu                TEXT,
    booking_links       TEXT,
    social_links        TEXT,
    reviews_fetched     INTEGER DEFAULT 0,
    reviews_cursor      TEXT DEFAULT '',
    reviews_total_saved INTEGER DEFAULT 0,
    scraped_at          TEXT DEFAULT (datetime('now')),
    -- Hotel / lodging
    hotel_class         TEXT,
    -- Status
    business_status     TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id               TEXT PRIMARY KEY,
    place_id                TEXT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    reviewer_name           TEXT,
    reviewer_profile_url    TEXT,
    reviewer_avatar_url     TEXT,
    reviewer_user_id        TEXT,
    reviewer_review_count   TEXT,
    reviewer_is_local_guide INTEGER,
    rating                  INTEGER,
    text                    TEXT,
    date                    TEXT,
    language                TEXT,
    photos                  TEXT,
    owner_reply             TEXT,
    owner_reply_date        TEXT,
    scraped_at              TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    query           TEXT,
    status          TEXT DEFAULT 'running',
    places_total    INTEGER DEFAULT 0,
    places_done     INTEGER DEFAULT 0,
    reviews_total   INTEGER DEFAULT 0,
    reviews_done    INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    error           TEXT
);

CREATE TABLE IF NOT EXISTS job_places (
    job_id          TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    place_id        TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    reviews_cursor  TEXT DEFAULT '',
    reviews_count   INTEGER DEFAULT 0,
    UNIQUE(job_id, place_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_places_reviews_fetched ON places(reviews_fetched);
CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
CREATE INDEX IF NOT EXISTS idx_job_places_job ON job_places(job_id);
CREATE INDEX IF NOT EXISTS idx_job_places_status ON job_places(status);
"""


def _to_json(obj):
    return json.dumps(obj) if obj is not None else None


def _bool_int(val):
    if val is None:
        return None
    return 1 if val else 0


class Database:
    """Thread-safe SQLite database with WAL mode and resume support."""

    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.executescript(_INIT_SQL)
            self._local.conn.commit()
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self.path)
        conn.executescript(_INIT_SQL)
        conn.commit()
        conn.close()

    def upsert_place(self, place):
        hours = None
        if place.opening_hours:
            hours = json.dumps({
                "periods": place.opening_hours.periods,
                "weekday_text": place.opening_hours.weekday_text,
                "open_now": place.opening_hours.open_now,
                "next_opening": place.opening_hours.next_opening,
            })
        self._conn().execute(
            """INSERT OR REPLACE INTO places
               (place_id, name, address, address_components, plus_code, lat, lng, rating, review_count,
                website, phone, email, fax, price_level, description, categories, primary_type, hours, photos,
                about, menu, booking_links, social_links,
                hotel_class, business_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                place.place_id, place.name, place.address,
                _to_json(place.address_components),
                place.plus_code,
                place.lat, place.lng, place.rating, place.review_count,
                place.website, place.phone, place.email, place.fax,
                place.price_level, place.description,
                _to_json(place.categories), place.primary_type,
                hours,
                _to_json(place.photos),
                _to_json(place.about),
                _to_json(place.menu),
                _to_json(place.booking_links),
                _to_json(place.social_links),
                place.hotel_class,

                place.business_status,
            ),
        )
        self._conn().commit()

    def insert_review(self, place_id, review):
        if not review.review_id:
            return
        self._conn().execute(
            """INSERT OR IGNORE INTO reviews
               (review_id, place_id, reviewer_name, reviewer_profile_url, reviewer_avatar_url,
                reviewer_user_id, reviewer_review_count, reviewer_is_local_guide,
                rating, text, date, language, photos, owner_reply, owner_reply_date)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                review.review_id, place_id,
                review.reviewer.name, review.reviewer.profile_url, review.reviewer.avatar_url,
                review.reviewer.user_id, review.reviewer.review_count,
                1 if review.reviewer.is_local_guide else 0,
                review.rating, review.text, review.date, review.language,
                _to_json(review.photos),
                review.owner_reply, review.owner_reply_date,
            ),
        )
        self._conn().commit()

    def mark_reviews_fetched(self, place_id, cursor="", total_saved=0):
        self._conn().execute(
            "UPDATE places SET reviews_fetched = 1, reviews_cursor = ?, reviews_total_saved = ? WHERE place_id = ?",
            (cursor, total_saved, place_id),
        )
        self._conn().commit()

    def get_place_cursor(self, place_id):
        row = self._conn().execute(
            "SELECT reviews_cursor, reviews_total_saved FROM places WHERE place_id = ?", (place_id,)
        ).fetchone()
        return {"cursor": row[0] if row else "", "total_saved": row[1] if row else 0}

    def get_pending_places(self):
        rows = self._conn().execute(
            "SELECT place_id, name, reviews_cursor, reviews_total_saved FROM places WHERE reviews_fetched = 0"
        ).fetchall()
        return [{"place_id": r[0], "name": r[1], "cursor": r[2] or "", "total_saved": r[3] or 0} for r in rows]

    def get_stats(self):
        c = self._conn().cursor()
        places = c.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        reviews = c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM places WHERE reviews_fetched = 0").fetchone()[0]
        return {"places": places, "reviews": reviews, "pending_reviews": pending}

    def get_place(self, place_id):
        row = self._conn().execute("SELECT * FROM places WHERE place_id = ?", (place_id,)).fetchone()
        return dict(row) if row else None

    # --- Job tracking ---

    def create_job(self, job_id, query):
        self._conn().execute(
            "INSERT OR IGNORE INTO jobs (job_id, query, status) VALUES (?, ?, 'running')",
            (job_id, query),
        )
        self._conn().commit()

    def add_job_places(self, job_id, place_ids):
        conn = self._conn()
        conn.executemany(
            "INSERT OR IGNORE INTO job_places (job_id, place_id, status) VALUES (?, ?, 'pending')",
            [(job_id, pid) for pid in place_ids],
        )
        conn.execute(
            "UPDATE jobs SET places_total = (SELECT COUNT(*) FROM job_places WHERE job_id = ?), updated_at = datetime('now') WHERE job_id = ?",
            (job_id, job_id),
        )
        conn.commit()

    def get_pending_job_places(self, job_id):
        rows = self._conn().execute(
            """SELECT jp.place_id, jp.reviews_cursor, p.name, p.reviews_total_saved
               FROM job_places jp
               LEFT JOIN places p ON jp.place_id = p.place_id
               WHERE jp.job_id = ? AND jp.status = 'pending'
               ORDER BY jp.rowid""",
            (job_id,),
        ).fetchall()
        return [{"place_id": r[0], "cursor": r[1] or "", "name": r[2] or "", "total_saved": r[3] or 0} for r in rows]

    def get_job_place_cursor(self, job_id, place_id):
        row = self._conn().execute(
            "SELECT reviews_cursor FROM job_places WHERE job_id = ? AND place_id = ?",
            (job_id, place_id),
        ).fetchone()
        return row[0] if row else ""

    def mark_job_place_done(self, job_id, place_id, reviews_count=0, cursor=""):
        conn = self._conn()
        conn.execute(
            """UPDATE job_places SET status = 'done', reviews_count = ?, reviews_cursor = ?
               WHERE job_id = ? AND place_id = ?""",
            (reviews_count, cursor, job_id, place_id),
        )
        conn.execute(
            """UPDATE jobs SET
                places_done = (SELECT COUNT(*) FROM job_places WHERE job_id = ? AND status = 'done'),
                reviews_done = (SELECT COALESCE(SUM(reviews_count), 0) FROM job_places WHERE job_id = ?),
                updated_at = datetime('now')
             WHERE job_id = ?""",
            (job_id, job_id, job_id),
        )
        conn.commit()

    def update_job_status(self, job_id, status, error=None):
        self._conn().execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = datetime('now') WHERE job_id = ?",
            (status, error, job_id),
        )
        self._conn().commit()

    def get_job(self, job_id):
        row = self._conn().execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit=20):
        rows = self._conn().execute(
            "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup_old_jobs(self, days=7):
        c = self._conn().execute(
            "DELETE FROM jobs WHERE created_at < datetime('now', '-{} days')".format(days)
        )
        self._conn().commit()
        return c.rowcount

    def vacuum(self):
        self._conn().execute("VACUUM")
        self._conn().commit()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
