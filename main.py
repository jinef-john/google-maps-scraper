"""CLI entry point for Google Maps scraper.

Usage:
    python main.py list "web developers in bangalore" --lat=12.97 --lng=77.59
    python main.py place "0x182f17eb1d447363:0x17a2d29bdcf01fda" --max-reviews=50
    python main.py search "hospitals in Nairobi" --max-places=5 --output results.json
"""

import argparse
import json
import logging
import sys

from scraper import GoogleMapsScraper


def _is_tty():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _print_place_summary(place_dict, index=None, reviews_fetched=None):
    """Print a compact multi-line summary of a place to stdout."""
    prefix = f"[{index}] " if index is not None else ""
    name = place_dict.get("name", "?")
    rating = place_dict.get("rating", 0)
    review_count = place_dict.get("review_count", 0)
    price = place_dict.get("price_level") or ""
    cats = ", ".join(place_dict.get("categories", [])[:2])
    phone = place_dict.get("phone", "")
    website = place_dict.get("website", "")
    address = place_dict.get("address", "")
    menu_cats = len(place_dict.get("menu", []))
    about_groups = len(place_dict.get("about", []))
    description = place_dict.get("description", "")
    reviews_note = f"  ({reviews_fetched} reviews fetched)" if reviews_fetched is not None else ""

    print(f"{prefix}{name}")
    print(f"  Rating:     {rating}/5  |  {review_count:,} reviews{('  |  ' + price) if price else ''}")
    if cats:
        print(f"  Category:   {cats}")
    if address:
        print(f"  Address:    {address}")
    if phone:
        print(f"  Phone:      {phone}")
    if website:
        print(f"  Website:    {website[:70]}")
    if description:
        print(f"  Desc:       {description[:100]}")
    if menu_cats:
        menu_items = sum(len(c["items"]) for c in place_dict.get("menu", []))
        print(f"  Menu:       {menu_cats} sections, {menu_items} items")
    if about_groups:
        print(f"  About:      {about_groups} attribute group(s)")
    if reviews_note:
        print(f"  Reviews:{reviews_note}")
    print()


class _StreamingWriter:
    """Streams a JSON array to a file, one object at a time."""

    def __init__(self, path):
        self._f = open(path, "w", encoding="utf-8")
        self._f.write("[\n")
        self._first = True

    def write(self, obj):
        if not self._first:
            self._f.write(",\n")
        self._f.write(json.dumps(obj, ensure_ascii=False, indent=2))
        self._f.flush()
        self._first = False

    def close(self):
        self._f.write("\n]\n")
        self._f.close()


def cmd_search(args):
    """Full search + scrape pipeline."""
    writer = _StreamingWriter(args.output) if args.output else None
    count = 0

    with GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        for place in scraper.search_and_scrape(
            query=args.query,
            lat=args.lat,
            lng=args.lng,
            zoom=args.zoom,
            max_places=args.max_places,
            max_reviews_per_place=args.max_reviews,
        ):
            count += 1
            place_dict = place.to_dict()

            if writer:
                writer.write(place_dict)

            if not args.quiet:
                if _is_tty() or not writer:
                    _print_place_summary(place_dict, index=count,
                                         reviews_fetched=len(place.reviews))
                else:
                    print(f"[{count}] {place_dict['name']} "
                          f"({place_dict['rating']}/5, {len(place.reviews)} reviews)")

    if writer:
        writer.close()
        print(f"Output written to: {args.output}", file=sys.stderr)

    if not writer and not _is_tty():
        # stdout is being piped — nothing was written yet, re-run is not ideal
        # for now this path is not reachable since we don't buffer
        pass

    print(f"Done. Scraped {count} place(s).", file=sys.stderr)


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

        if not place:
            print("Failed to fetch place details.", file=sys.stderr)
            sys.exit(1)

        place_dict = place.to_dict()

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump([place_dict], f, ensure_ascii=False, indent=2)
            print(f"Output written to: {args.output}", file=sys.stderr)
        elif _is_tty():
            _print_place_summary(place_dict, reviews_fetched=len(place.reviews))
        else:
            print(json.dumps(place_dict, ensure_ascii=False))

        print(f"Scraped: {place_dict['name']} "
              f"({place_dict['rating']}/5, {len(place.reviews)} reviews fetched)",
              file=sys.stderr)


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

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Output written to: {args.output}", file=sys.stderr)
    elif _is_tty():
        for i, r in enumerate(results, 1):
            cats = ", ".join(r.get("categories", [])[:2])
            rating = r.get("rating") or ""
            print(f"  [{i}] {r.get('name', '?')}"
                  f"{('  |  ' + str(rating) + '/5') if rating else ''}"
                  f"{('  |  ' + cats) if cats else ''}")
            print(f"       {r['place_id']}")
    else:
        print(json.dumps(results, ensure_ascii=False))

    print(f"\nFound {len(results)} place(s).", file=sys.stderr)


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
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser("search", help="Search and scrape places")
    p_search.add_argument("query", help="Search query (e.g. 'hospitals in Nairobi')")
    p_search.add_argument("--lat", type=float, default=0.0, help="Search center latitude")
    p_search.add_argument("--lng", type=float, default=0.0, help="Search center longitude")
    p_search.add_argument("--zoom", type=int, default=13, help="Map zoom level (default: 13)")
    p_search.add_argument("--max-places", type=int, default=20, help="Max places to scrape")
    p_search.add_argument("--max-reviews", type=int, default=50, help="Max reviews per place")
    p_search.add_argument("--output", "-o", help="Output JSON file path")

    p_place = subparsers.add_parser("place", help="Scrape a single place by ID")
    p_place.add_argument("place_id", help="Hex place ID (e.g. 0x182f17eb1d447363:0x17a2d29bdcf01fda)")
    p_place.add_argument("--lat", type=float, default=0.0, help="Place latitude")
    p_place.add_argument("--lng", type=float, default=0.0, help="Place longitude")
    p_place.add_argument("--max-reviews", type=int, default=100, help="Max reviews to fetch")
    p_place.add_argument("--output", "-o", help="Output JSON file path")

    p_list = subparsers.add_parser("list", help="Search and list places (no details)")
    p_list.add_argument("query", help="Search query")
    p_list.add_argument("--lat", type=float, default=0.0, help="Search center latitude")
    p_list.add_argument("--lng", type=float, default=0.0, help="Search center longitude")
    p_list.add_argument("--zoom", type=int, default=13, help="Map zoom level")
    p_list.add_argument("--max-places", type=int, default=60, help="Max results")
    p_list.add_argument("--output", "-o", help="Output JSON file path")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    commands = {"search": cmd_search, "place": cmd_place, "list": cmd_list}
    commands[args.command](args)


if __name__ == "__main__":
    main()
