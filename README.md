# gmaps-scraper

A request-based Google Maps scraper that extracts place information and reviews.

## Install

```bash
pip install -r requirements.txt
```

## Usage

### Search for places

```bash
python main.py list "web developers in Stockholm" --max-places=20
python main.py list "hospitals in Stockholm" --max-places=10
```

### Get full details + reviews for a place

- uses known place id

```bash
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=20
```

### Search + scrape all results (details + reviews)

```bash
python main.py search "Havard University" --max-reviews=40
```

### Save output to file

```bash
python main.py search "coffee shops in London" --max-reviews=10  --max-places=10 --output coffee.json
python main.py list "web developers in Stockholm" --max-places=5 --output out.json
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=20 --output output.json
```

## Commands

| Command  | What it does                                | Speed  | Returns                                      |
| -------- | ------------------------------------------- | ------ | -------------------------------------------- |
| `list`   | Search only — no details or reviews fetched | Fast   | name, address, rating, coords, categories    |
| `place`  | Full scrape of a single known place         | Medium | all fields + reviews                         |
| `search` | Search + full scrape of every result        | Slow   | all fields + reviews for every matched place |

**`list`** — Use this to discover places and their IDs. Makes one request per page of results. Does not fetch phone numbers, opening hours, or reviews.

```bash
python main.py list "web developers in Stockholm" --max-places=20
# → quick list of matching places with place_id values
```

**`place`** — Use this when you already have a `place_id` (from `list` or elsewhere) and want everything: full address components, phone, opening hours, and all reviews.

```bash
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=100
# → complete data for that one place
```

**`search`** — Combines both steps: runs a search then scrapes full details and reviews for every result. Most data, most requests.

```bash
python main.py search "hospitals in Nairobi" --max-places=5 --max-reviews=20
# → full data for up to 5 matching places
```

**Typical workflow:**

```bash
# Step 1: find places and note the place_id
python main.py list "coffee shops in Paris" --max-places=20 --output places.json

# Step 2: scrape a specific one in full
python main.py place "0x47e66e1f06e2b70f:0x40b82c3688c9460" --output details.json
```

## Options

| Flag            | Description                                | Default                      |
| --------------- | ------------------------------------------ | ---------------------------- |
| `--max-places`  | Max number of places to return             | 20                           |
| `--max-reviews` | Max reviews to fetch per place             | 50 (`search`), 100 (`place`) |
| `--lat / --lng` | Center coordinates (optional)              | 0                            |
| `--proxy`       | Proxy URL (`socks5://...` or `http://...`) | None                         |
| `--lang`        | Language code                              | `en`                         |
| `--gl`          | Country/region code                        | `us`                         |
| `--delay`       | Seconds between requests                   | 1.5                          |
| `--output`      | Save JSON output to file                   | stdout                       |

## What it extracts

- Name, address, coordinates
- Rating, review count
- Categories, website, phone number
- Opening hours
- Reviews with: author, rating, text, date, owner reply, language

# Contributions are welcome!
