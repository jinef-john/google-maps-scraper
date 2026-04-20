#!/usr/bin/env python3
"""CLI entry point for Google Maps Scraper.

Usage:
    python -m gmaps_scraper search "hospitals in Nairobi" --lat -1.286 --lng 36.817
    python -m gmaps_scraper place "0x182f17eb1d447363:0x17a2d29bdcf01fda" --lat -1.253 --lng 36.859
    python -m gmaps_scraper full "web developers in bangalore" --lat 12.97 --lng 77.59
"""

import argparse
import json
import logging
import sys

from .scraper import GoogleMapsScraper


def main():
    parser = argparse.ArgumentParser(
        prog="gmaps_scraper",
        description="Google Maps place scraper - extract info, reviews, and more",
    )
    parser.add_argument("--proxy", default=None, help="Proxy URL (socks5://... or http://...)")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument("--gl", default="us", help="Country code (default: us)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Min delay between requests (seconds)")
    parser.add_argument("--max-delay", type=float, default=3.0, help="Max delay between requests (seconds)")
    parser.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- search command ---
    search_parser = subparsers.add_parser("search", help="Search for places")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--lat", type=float, default=0.0, help="Center latitude")
    search_parser.add_argument("--lng", type=float, default=0.0, help="Center longitude")
    search_parser.add_argument("--zoom", type=int, default=13, help="Zoom level")
    search_parser.add_argument("--max-results", type=int, default=60, help="Max results")

    # --- place command ---
    place_parser = subparsers.add_parser("place", help="Get full details for a place")
    place_parser.add_argument("place_id", help="Hex place ID (0x...:0x...)")
    place_parser.add_argument("--lat", type=float, default=0.0, help="Place latitude")
    place_parser.add_argument("--lng", type=float, default=0.0, help="Place longitude")
    place_parser.add_argument("--query", default="", help="Search context query")
    place_parser.add_argument("--max-reviews", type=int, default=100, help="Max reviews to fetch")

    # --- full command ---
    full_parser = subparsers.add_parser("full", help="Search + scrape all places with reviews")
    full_parser.add_argument("query", help="Search query")
    full_parser.add_argument("--lat", type=float, default=0.0, help="Center latitude")
    full_parser.add_argument("--lng", type=float, default=0.0, help="Center longitude")
    full_parser.add_argument("--zoom", type=int, default=13, help="Zoom level")
    full_parser.add_argument("--max-places", type=int, default=20, help="Max places to scrape")
    full_parser.add_argument("--max-reviews", type=int, default=50, help="Max reviews per place")

    # --- reviews command ---
    reviews_parser = subparsers.add_parser("reviews", help="Get reviews for a place")
    reviews_parser.add_argument("place_id", help="Hex place ID (0x...:0x...)")
    reviews_parser.add_argument("--max-reviews", type=int, default=100, help="Max reviews to fetch")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Run the appropriate command
    with GoogleMapsScraper(proxy=args.proxy, timeout=args.timeout, lang=args.lang, gl=args.gl) as scraper:
        scraper.set_delay(args.min_delay, args.max_delay)

        if args.command == "search":
            results = scraper.search(
                query=args.query,
                lat=args.lat,
                lng=args.lng,
                zoom=args.zoom,
                max_results=args.max_results,
            )
            output = results

        elif args.command == "place":
            place = scraper.scrape_place(
                place_id=args.place_id,
                lat=args.lat,
                lng=args.lng,
                query=args.query,
                max_reviews=args.max_reviews,
            )
            output = place.to_dict() if place else {"error": "Place not found"}

        elif args.command == "reviews":
            reviews = scraper.get_all_reviews(
                place_id=args.place_id,
                max_reviews=args.max_reviews,
            )
            output = [
                {
                    "reviewer": {
                        "name": r.reviewer.name,
                        "profile_url": r.reviewer.profile_url,
                        "review_count": r.reviewer.review_count,
                        "is_local_guide": r.reviewer.is_local_guide,
                    },
                    "rating": r.rating,
                    "text": r.text,
                    "date": r.date,
                    "photos": r.photos,
                    "owner_reply": r.owner_reply,
                    "language": r.language,
                }
                for r in reviews
            ]

        elif args.command == "full":
            output = []
            for place in scraper.search_and_scrape(
                query=args.query,
                lat=args.lat,
                lng=args.lng,
                zoom=args.zoom,
                max_places=args.max_places,
                max_reviews_per_place=args.max_reviews,
            ):
                output.append(place.to_dict())

    # Write output
    json_output = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_output)
        logging.getLogger(__name__).info(f"Results written to {args.output}")
    else:
        print(json_output)


if __name__ == "__main__":
    main()
