<!-- logo -->
<p align="center">
  <img src="assets/logo.png" alt="gmaps-request" width="180"/>
</p>

<p align="center">
  <b>Fast, lightweight HTTP-based Google Maps scraper for places & reviews.</b>
</p>

<!-- core badges -->
<p align="center">
  <img src="https://img.shields.io/github/stars/jinef-john/google-maps-scraper?style=flat-square" />
  <img src="https://img.shields.io/github/forks/jinef-john/google-maps-scraper?style=flat-square" />
  <img src="https://img.shields.io/github/issues/jinef-john/google-maps-scraper?style=flat-square" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/type-HTTP--based-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/output-SQLite-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/speed-fast-brightgreen?style=flat-square" />
  <img src="https://img.shields.io/badge/resume-supported-blueviolet?style=flat-square" />
  <img src="https://img.shields.io/badge/use%20case-lead%20generation-yellow?style=flat-square" />
</p>

---

A request-based scraper that extracts Google Maps place data and reviews without browser automation.

**Key features:**

- **Concurrency** -> Parallel workers with independent sessions
- **Resume support** -> Job tracking + per-place review resumption from saved cursors
- **Session persistence** -> 0-RTT TLS resumption via `session.json`
- **Rate limit handling** -> Exponential backoff + connection refresh on 429
- **WAL-mode SQLite** -> Concurrent reads/writes without lock contention

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

## Quick Start

```bash
# Search + scrape places and reviews
python main.py search "restaurants in Paris" --max-places=20 --max-reviews=50

# Scrape a single place by ID
python main.py place "0x89e377427d7f0199:0x5937c65cee2427f0" --max-reviews=200

# Search only (fast discovery, no details/reviews)
python main.py list "hotels in Dubai" --max-places=30

# Resume an interrupted job
python main.py resume <job_id> --max-reviews=100

# Database stats
python main.py stats
```

## Commands

| Command  | Description                       | Returns                                       |
| -------- | --------------------------------- | --------------------------------------------- |
| `search` | Search + full scrape              | All fields + reviews                          |
| `place`  | Scrape a single known place       | All fields + reviews (resumes from DB cursor) |
| `list`   | Search only -> no details/reviews | Name, address, rating, coords, categories     |
| `resume` | Resume a job                      | Continues from last saved cursor per place    |
| `stats`  | Database statistics               | Place count, review count, pending jobs       |

## Options

| Flag             | Description                                      | Default               |
| ---------------- | ------------------------------------------------ | --------------------- |
| `--db`           | SQLite database path                             | `output/gmaps.db`     |
| `--max-places`   | Max places to scrape (`None` = unlimited)        | unlimited             |
| `--max-reviews`  | Max reviews per place (`None` = all, `0` = skip) | unlimited             |
| `--workers`      | Concurrent workers                               | 4                     |
| `--delay`        | Min seconds between requests                     | 2.5                   |
| `--proxy`        | Proxy URL (`socks5://...` or `http://...`)       | None                  |
| `--session-file` | Session persistence path                         | `output/session.json` |
| `--lang`         | Language code                                    | `en`                  |
| `--gl`           | Country/region code                              | `us`                  |

## Typical Workflows

### Discover first, scrape selected places later

```bash
python main.py list "coffee shops in Amsterdam" --max-places=20
python main.py place "0x47c609c7..." --max-reviews=200
```

### Scrape details now, reviews later

```bash
python main.py search "restaurants in Nairobi" --max-places=20 --max-reviews=0
python main.py resume <job_id> --max-reviews=300
```

### Large-scale scraping

```bash
python main.py search "hotels in London" --max-places=100 --max-reviews=50 --workers=8
```

## How Resume Works

- **`search` / `place`** --> Saves a pagination cursor per place in the database
- **`resume <job_id>`** --> Re-opens places that need more reviews and continues from their saved cursors
- **`place` repeat runs** --> Skips if you already have enough reviews; fetches more if you increased `--max-reviews`

## Disclaimer

> This tool is provided for educational and research purposes. By using it, you agree to comply with applicable laws regarding data collection.
