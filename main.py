"""CLI entry point for Google Maps scraper.

Usage:
    # Search and scrape all places for a query
    python main.py search "hospitals in Nairobi" --lat=-1.286 --lng=36.817

    # Get details + reviews for a specific place
    python main.py place "0x182f17eb1d447363:0x17a2d29bdcf01fda" --lat=-1.253 --lng=36.859

    # Search only (no details/reviews)
    python main.py list "web developers in bangalore" --lat=12.97 --lng=77.59
"""

import argparse
import json
import logging
import sys

from gmaps_scraper import GoogleMapsScraper


def cmd_search(args):
    """Full search + scrape pipeline."""
    with GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        places = []
        for place in scraper.search_and_scrape(
            query=args.query,
            lat=args.lat,
            lng=args.lng,
            zoom=args.zoom,
            max_places=args.max_places,
            max_reviews_per_place=args.max_reviews,
        ):
            place_dict = place.to_dict()
            places.append(place_dict)

            if not args.quiet:
                print(f"[{len(places)}] {place_dict['name']} "
                      f"({place_dict['rating']}/5, {place_dict['review_count']} reviews)")

        _output(places, args.output)
        print(f"\nDone. Scraped {len(places)} places.", file=sys.stderr)


def cmd_place(args):
    """Scrape a single place by ID."""
    with GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        place = scraper.scrape_place(
            place_id=args.place_id,
            lat=args.lat,
            lng=args.lng,
            max_reviews=args.max_reviews,
        )

        if place:
            place_dict = place.to_dict()
            _output([place_dict], args.output)
            print(f"\nScraped: {place_dict['name']} "
                  f"({place_dict['rating']}/5, {len(place.reviews)} reviews fetched)",
                  file=sys.stderr)
        else:
            print("Failed to fetch place details.", file=sys.stderr)
            sys.exit(1)


def cmd_list(args):
    """Search only - list places without scraping details."""
    with GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        results = scraper.search(
            query=args.query,
            lat=args.lat,
            lng=args.lng,
            zoom=args.zoom,
            max_results=args.max_places,
        )

        _output(results, args.output)

        if not args.quiet:
            for i, r in enumerate(results, 1):
                print(f"  [{i}] {r.get('name', '?')} | {r['place_id']}")

        print(f"\nFound {len(results)} places.", file=sys.stderr)


def _output(data, output_file):
    """Write JSON output to file or stdout."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Output written to: {output_file}", file=sys.stderr)
    else:
        print(json_str)


def main():
    parser = argparse.ArgumentParser(
        description="Google Maps Scraper - Extract place info, reviews, and more",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--proxy", help="Proxy URL (socks5://..., http://...)")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument("--gl", default="us", help="Country code (default: us)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Min delay between requests in seconds (default: 1.5)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search command
    p_search = subparsers.add_parser("search", help="Search and scrape places")
    p_search.add_argument("query", help="Search query (e.g. 'hospitals in Nairobi')")
    p_search.add_argument("--lat", type=float, default=0.0, help="Search center latitude")
    p_search.add_argument("--lng", type=float, default=0.0, help="Search center longitude")
    p_search.add_argument("--zoom", type=int, default=13, help="Map zoom level (default: 13)")
    p_search.add_argument("--max-places", type=int, default=20, help="Max places to scrape")
    p_search.add_argument("--max-reviews", type=int, default=50, help="Max reviews per place")

    # place command
    p_place = subparsers.add_parser("place", help="Scrape a single place by ID")
    p_place.add_argument("place_id", help="Hex place ID (e.g. 0x182f17eb1d447363:0x17a2d29bdcf01fda)")
    p_place.add_argument("--lat", type=float, default=0.0, help="Place latitude")
    p_place.add_argument("--lng", type=float, default=0.0, help="Place longitude")
    p_place.add_argument("--max-reviews", type=int, default=100, help="Max reviews to fetch")

    # list command
    p_list = subparsers.add_parser("list", help="Search and list places (no details)")
    p_list.add_argument("query", help="Search query")
    p_list.add_argument("--lat", type=float, default=0.0, help="Search center latitude")
    p_list.add_argument("--lng", type=float, default=0.0, help="Search center longitude")
    p_list.add_argument("--zoom", type=int, default=13, help="Map zoom level")
    p_list.add_argument("--max-places", type=int, default=60, help="Max results")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    commands = {
        "search": cmd_search,
        "place": cmd_place,
        "list": cmd_list,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
