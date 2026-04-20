# gmaps-scraper

A request-based Google Maps scraper that extracts place information and reviews.

## Install

```bash
pip install httpcloak
```

## Usage

### Search for places

```bash
python main.py list "web developers in Stockholm"
python main.py list "hospitals in Stockholm" --max-places=10
```

### Get full details + reviews for a place

```bash
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --max-reviews=50
```

### Search + scrape all results (details + reviews)

```bash
python main.py search "Havard University" --max-places=3
```

### Save output to file

```bash
python main.py search "coffee shops in London" --output results.json
python main.py list "web developers in Stockholm" --max-places=5 --output out.json
python main.py place "0x465f9b8fa03f30b3:0xb52faeba880b7674" --output output.json
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

## Project structure

```
├── main.py          # CLI entry point
├── scraper.py       # Main orchestrator
├── helpers/
│   ├── client.py    # httpcloak session wrapper
│   ├── endpoints.py # URL builders
│   └── parsers.py   # Response parsers
├── models/
│   └── __init__.py  # Place, Review, Reviewer dataclasses
└── utils/
    ├── __init__.py  # Helper utilities
    └── pb.py        # Protobuf-style URL encoder
```
