import argparse
import logging
import sys

from db import Database
from scraper import GoogleMapsScraper


def _print_place_summary(place, index=None, reviews_saved=None):
    prefix = f"[{index}] " if index is not None else ""
    price = place.price_level or ""
    cats = ", ".join(place.categories[:2])
    menu_count = len(place.menu)
    about_count = len(place.about)

    print(f"{prefix}{place.name}")
    print(f"  Rating:   {place.rating}/5  |  {place.review_count:,} reviews{('  |  ' + price) if price else ''}")
    if cats:              print(f"  Category: {cats}")
    if place.address:    print(f"  Address:  {place.address}")
    if place.phone:      print(f"  Phone:    {place.phone}")
    if place.website:    print(f"  Website:  {place.website[:70]}")
    if place.description: print(f"  Desc:     {place.description[:100]}")
    if menu_count:
        menu_items = sum(len(s["items"]) for s in place.menu)
        print(f"  Menu:     {menu_count} sections, {menu_items} items")
    if about_count:      print(f"  About:    {about_count} attribute group(s)")
    if reviews_saved is not None:
        print(f"  Reviews:  {reviews_saved} saved")
    print()


def cmd_search(args):
    with Database(args.db) as db, GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        results = scraper.search(
            query=args.query, lat=args.lat, lng=args.lng,
            zoom=args.zoom, max_results=args.max_places,
        )

        for i, result in enumerate(results, 1):
            place = scraper.get_place_details(
                place_id=result["place_id"],
                lat=result.get("lat", 0.0),
                lng=result.get("lng", 0.0),
                query=args.query,
            )
            if not place:
                continue

            db.upsert_place(place)
            reviews_saved = 0
            for review in scraper.iter_reviews(result["place_id"], args.max_reviews):
                db.insert_review(result["place_id"], review)
                reviews_saved += 1

            if not args.quiet:
                _print_place_summary(place, index=i, reviews_saved=reviews_saved)

    print(f"Done. {len(results)} place(s) saved to {args.db}", file=sys.stderr)


def cmd_place(args):
    with Database(args.db) as db, GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)

        place = scraper.get_place_details(
            place_id=args.place_id,
            lat=args.lat,
            lng=args.lng,
        )
        if not place:
            print("Failed to fetch place details.", file=sys.stderr)
            sys.exit(1)

        db.upsert_place(place)
        reviews_saved = 0
        for review in scraper.iter_reviews(args.place_id, args.max_reviews):
            db.insert_review(args.place_id, review)
            reviews_saved += 1

    _print_place_summary(place, reviews_saved=reviews_saved)
    print(f"Saved to {args.db}", file=sys.stderr)


def cmd_list(args):
    with GoogleMapsScraper(proxy=args.proxy, lang=args.lang, gl=args.gl) as scraper:
        if args.delay:
            scraper.set_delay(args.delay, args.delay * 2)
        results = scraper.search(
            query=args.query, lat=args.lat, lng=args.lng,
            zoom=args.zoom, max_results=args.max_places,
        )

    for i, r in enumerate(results, 1):
        cats = ", ".join(r.get("categories", [])[:2])
        rating = r.get("rating") or ""
        print(f"  [{i}] {r.get('name', '?')}"
              f"{('  |  ' + str(rating) + '/5') if rating else ''}"
              f"{('  |  ' + cats) if cats else ''}")
        print(f"       {r['place_id']}")

    print(f"\nFound {len(results)} place(s).", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Google Maps Scraper")
    parser.add_argument("--proxy", help="Proxy URL (socks5://..., http://...)")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument("--gl", default="us", help="Country code (default: us)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Min delay between requests in seconds (default: 1.5)")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser("search", help="Search and scrape places")
    p_search.add_argument("query")
    p_search.add_argument("--lat", type=float, default=0.0)
    p_search.add_argument("--lng", type=float, default=0.0)
    p_search.add_argument("--zoom", type=int, default=13)
    p_search.add_argument("--max-places", type=int, default=20)
    p_search.add_argument("--max-reviews", type=int, default=50)
    p_search.add_argument("--db", default="output/gmaps.db", help="SQLite output (default: output/gmaps.db)")

    p_place = subparsers.add_parser("place", help="Scrape a single place by ID")
    p_place.add_argument("place_id")
    p_place.add_argument("--lat", type=float, default=0.0)
    p_place.add_argument("--lng", type=float, default=0.0)
    p_place.add_argument("--max-reviews", type=int, default=100)
    p_place.add_argument("--db", default="output/gmaps.db", help="SQLite output (default: output/gmaps.db)")

    p_list = subparsers.add_parser("list", help="Search and list places (no scraping)")
    p_list.add_argument("query")
    p_list.add_argument("--lat", type=float, default=0.0)
    p_list.add_argument("--lng", type=float, default=0.0)
    p_list.add_argument("--zoom", type=int, default=13)
    p_list.add_argument("--max-places", type=int, default=60)

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    {"search": cmd_search, "place": cmd_place, "list": cmd_list}[args.command](args)


if __name__ == "__main__":
    main()
