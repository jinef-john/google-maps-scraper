# gmaps-scraper

A request-based Google Maps scraper that extracts place information and reviews. Light weight and fast.

## Install

```bash
pip install -r requirements.txt
```

## Usage

- sqlite3: Default db path is `output/gmaps.db` but you can specify any path with `--db`.

### List places (search only, no scraping)

```bash
python main.py list "web developers in Stockholm" --max-places=20
python main.py list "hospitals in Nairobi"
```

### Scrape a single place by ID

```bash
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=100 --db output/places.db
```

### Search and scrape all results

```bash
python main.py search "coffee shops in London" --max-places=10 --max-reviews=50 --db output/london.db
python main.py search "restaurants in Nairobi" --db output/nairobi.db
```

### Place details only, no reviews

```bash
python main.py search "hotels in London" --max-places=20 --max-reviews=0
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=0
```

## Commands

| Command  | What it does                                | Returns                                      |
| -------- | ------------------------------------------- | -------------------------------------------- |
| `list`   | Search only - no details or reviews fetched | name, address, rating, coords, categories    |
| `place`  | Full scrape of a single known place         | all fields + reviews → saved to DB           |
| `search` | Search + full scrape of every result        | all fields + reviews for every matched place |

**`list`** -> Discover places and their IDs. One request per page. Does not fetch phone, opening hours, or reviews.

```bash
python main.py list "web developers in Stockholm" --max-places=20
# → quick list with place_id values
```

**`place`** -> Use when you already have a `place_id` (from `list` or elsewhere). Fetches full details and reviews, saves to DB.

```bash
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=100 --db output/places.db
```

**`search`** -> Runs a search then scrapes full details and reviews for every result. Most data, most requests.

```bash
python main.py search "hospitals in Nairobi" --max-places=5 --max-reviews=20 --db output/nairobi.db
```

**Typical workflow:**

```bash
# Step 1: find places and note the place_id
python main.py list "coffee shops in Paris" --max-places=20

# Step 2: scrape a specific one in full
python main.py place "0x47e671fd3387e0dd:0x174ea8ece7dffa45" --max-reviews=200 --db output/paris.db

```

## Options

| Flag            | Description                                | Default                      |
| --------------- | ------------------------------------------ | ---------------------------- |
| `--db`          | SQLite database path                       | `output/gmaps.db`            |
| `--max-places`  | Max number of places to return             | 20                           |
| `--max-reviews` | Max reviews per place (`0` = skip reviews) | 50 (`search`), 100 (`place`) |
| `--lat / --lng` | Center coordinates (optional)              | 0                            |
| `--proxy`       | Proxy URL (`socks5://...` or `http://...`) | None                         |
| `--lang`        | Language code                              | `en`                         |
| `--gl`          | Country/region code                        | `us`                         |
| `--delay`       | Min seconds between requests               | 1.5                          |

## Database schema

Results are saved to two tables:

**`places`** -> one row per place, upserted on `place_id`

- `place_id`, `name`, `address`, `lat`, `lng`, `rating`, `review_count`
- `website`, `phone`, `price_level`, `description`
- `categories`, `hours`, `photos`, `about`, `menu`, `booking_links` (JSON columns)
- `reviews_fetched` - `0` if only place details were saved, `1` once reviews have been fetched

Use `reviews_fetched` to find places that still need reviews scraped:

```sql
SELECT place_id, name FROM places WHERE reviews_fetched = 0;
```

**`reviews`** -> one row per review, deduplicated on `review_id`

- `review_id`, `place_id`, `reviewer_name`, `reviewer_profile_url`, `reviewer_is_local_guide`
- `rating`, `text`, `date`, `language`, `photos`, `owner_reply`, `owner_reply_date`

## What the scraper extracts

**Place info**

- Name, address, coordinates
- Rating, review count, price level
- Categories, website, phone number
- Opening hours
- Description (editorial summary)
- About section: services, accessibility, dining options, amenities (grouped yes/no attributes)
- Menu items with name, description, price (restaurants only)
- Booking / reservation links (OpenTable, TheFork, etc.)

**Reviews**

- Author name, profile URL, avatar, review count, local guide badge
- Rating, text, language, date
- Review photos (direct image URLs)
- Owner reply text and date

# Contributions are welcome!

## Disclaimer

> This Scraper is provided for educational and research purposes only. By using it, you agree to comply with local and international laws regarding data scraping and privacy. The authors and contributors are not responsible for any misuse of this software. This tool should not be used to violate the rights of others, or for unethical purposes.
