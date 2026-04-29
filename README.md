# gmaps-request

A request-based Google Maps scraper that extracts place information and reviews. Light weight and super fast.

## Why gmaps-request?

It's a solid alternative to browser automation tools when you need structured data without the overhead of rendering. Key features include:

- **Concurrency** - Parallel scraping with independent sessions per worker
- **Resume support** - Job tracking + per-place review resumption
- **Session persistence** - 0-RTT TLS resumption via save/load
- **Rate limit handling** - Exponential backoff with connection refresh on 429
- **WAL-mode SQLite** - Concurrent reads/writes without lock contention

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

## Quick Start

```bash
# Search + scrape all results
python main.py search "restaurants in Paris" --max-places=20 --max-reviews=50

# Scrape a single place by ID
python main.py place "0x47e671fd3387e0dd:0x174ea8ece7dffa45" --max-reviews=200

# List only (fast discovery)
python main.py list "hotels in Dubai" --max-places=30

# Resume an interrupted job
python main.py resume <job_id>

# Database stats
python main.py stats
```

## Commands

| Command  | Description                          | Returns                                   |
| -------- | ------------------------------------ | ----------------------------------------- |
| `search` | Search + full scrape of every result | All fields + reviews per place            |
| `place`  | Full scrape of a single known place  | All fields + reviews                      |
| `list`   | Search only - no details or reviews  | name, address, rating, coords, categories |
| `resume` | Resume an interrupted scraping job   | Continues from last saved state           |
| `stats`  | Show database statistics             | Place count, review count, pending jobs   |

## Options

| Flag             | Description                            | Default               |
| ---------------- | -------------------------------------- | --------------------- |
| `--db`           | SQLite database path                   | `output/gmaps.db`     |
| `--max-places`   | Max places to scrape                   | 20                    |
| `--max-reviews`  | Max reviews per place (0 = skip)       | 50                    |
| `--workers`      | Concurrent workers                     | 4                     |
| `--delay`        | Min seconds between requests           | 1.5                   |
| `--proxy`        | Proxy URL (socks5://... or http://...) | None                  |
| `--session-file` | Session persistence path               | `output/session.json` |
| `--job-id`       | Custom job ID for tracking/resume      | (auto)                |
| `--lang`         | Language code                          | `en`                  |
| `--gl`           | Country/region code                    | `us`                  |
| `--quiet`        | Suppress progress output               | False                 |
| `--verbose`      | Debug logging                          | False                 |

## How It Uses httpcloak

| Feature                | How We Use It                                         |
| ---------------------- | ----------------------------------------------------- |
| **TLS fingerprinting** | `chrome-146-windows` preset                           |
| **Warmup**             | Visits google.com and google.com/maps before scraping |
| **Session resumption** | Saves/loads `session.json` for 0-RTT reconnects       |
| **Refresh**            | Resets connections on rate limit, keeps TLS cache     |
| **Retry + backoff**    | 3 attempts with exponential backoff                   |
| **Proxy rotation**     | Runtime proxy switching                               |

## Resume Architecture

Three layers of resume protection:

1. **Job tracking** - `jobs` + `job_places` tables track every place's status
2. **Review cursor** - `reviews_cursor` column saves the pagination cursor per place
3. **Session persistence** - `session.json` enables 0-RTT TLS resumption between runs

## Typical Workflows

### Discover places first, then scrape selected ones

```bash
python main.py list "coffee shops in Amsterdam" --max-places=20
python main.py place "0x47c609c7..." --max-reviews=200 --db amsterdam.db
```

### Large-scale scraping with concurrency

```bash
python main.py search "hotels in London" --max-places=100 --max-reviews=50 --workers=8 --db london.db
```

### Resume after interruption

```bash
python main.py search "restaurants in Tokyo" --max-places=500 --job-id=tokyo_r1
python main.py resume tokyo_r1 --workers=8
```

### You can open issues for bug reports, feature requests, or questions. Pull requests are also welcome if you'd like to contribute code or improvements.

## Disclaimer

> This tool is provided for educational and research purposes. By using it, you agree to comply with applicable laws regarding data collection.
