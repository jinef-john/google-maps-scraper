import json
import os
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
    place_id      TEXT PRIMARY KEY,
    name          TEXT,
    address       TEXT,
    address_components TEXT,
    lat           REAL,
    lng           REAL,
    rating        REAL,
    review_count  INTEGER,
    website       TEXT,
    phone         TEXT,
    price_level   TEXT,
    description   TEXT,
    categories    TEXT,
    hours         TEXT,
    photos        TEXT,
    about         TEXT,
    menu          TEXT,
    booking_links TEXT,
    reviews_fetched INTEGER DEFAULT 0,
    scraped_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id              TEXT PRIMARY KEY,
    place_id               TEXT NOT NULL REFERENCES places(place_id),
    reviewer_name          TEXT,
    reviewer_profile_url   TEXT,
    reviewer_avatar_url    TEXT,
    reviewer_user_id       TEXT,
    reviewer_review_count  TEXT,
    reviewer_is_local_guide INTEGER,
    rating                 INTEGER,
    text                   TEXT,
    date                   TEXT,
    language               TEXT,
    photos                 TEXT,
    owner_reply            TEXT,
    owner_reply_date       TEXT
);
"""


class Database:
    def __init__(self, path):
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def upsert_place(self, place):
        hours = None
        if place.opening_hours:
            hours = json.dumps({
                "periods": place.opening_hours.periods,
                "weekday_text": place.opening_hours.weekday_text,
            })
        self.conn.execute(
            """INSERT OR REPLACE INTO places
               (place_id, name, address, address_components, lat, lng, rating, review_count,
                website, phone, price_level, description, categories, hours, photos, about,
                menu, booking_links)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                place.place_id, place.name, place.address,
                json.dumps(place.address_components),
                place.lat, place.lng, place.rating, place.review_count,
                place.website, place.phone, place.price_level, place.description,
                json.dumps(place.categories),
                hours,
                json.dumps(place.photos),
                json.dumps(place.about),
                json.dumps(place.menu),
                json.dumps(place.booking_links),
            ),
        )
        self.conn.commit()

    def insert_review(self, place_id, review):
        if not review.review_id:
            return
        self.conn.execute(
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
                json.dumps(review.photos),
                review.owner_reply, review.owner_reply_date,
            ),
        )
        self.conn.commit()

    def mark_reviews_fetched(self, place_id):
        self.conn.execute(
            "UPDATE places SET reviews_fetched = 1 WHERE place_id = ?", (place_id,)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
