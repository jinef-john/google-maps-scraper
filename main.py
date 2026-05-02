"""CLI for gmaps-request."""

import argparse
import hashlib
import logging
import sys
import time

from db import Database
from scraper import GoogleMapsScraper


def _setup_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s" if verbose else "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stderr)


def _print_place(place, index=None, reviews_saved=None):
    prefix = f"[{index}] " if index else ""
    cats = ", ".join(place.categories[:2])
    print(f"\n{prefix}{place.name}")
    print(f"  Rating:   {place.rating}/5  |  {place.review_count:,} reviews", end="")
    if place.price_level:
        print(f"  |  {place.price_level}", end="")
    print()
    if cats:
        print(f"  Category: {cats}")
    if place.address:
        print(f"  Address:  {place.address}")
    if place.phone:
        print(f"  Phone:    {place.phone}")
    if place.email:
        print(f"  Email:    {place.email}")
    if place.website:
        print(f"  Website:  {place.website[:70]}")
    if place.social_links:
        for link in place.social_links[:3]:
            print(f"  {link['platform'].capitalize()}: {link['url'][:70]}")
    if place.description:
        print(f"  Desc:     {place.description[:100]}")
    if place.menu:
        items = sum(len(s["items"]) for s in place.menu)
        print(f"  Menu:     {len(place.menu)} sections, {items} items")
    if place.about:
        print(f"  About:    {len(place.about)} attribute group(s)")
    if place.hotel_class:
        print(f"  Hotel:    {place.hotel_class}")
    if place.hotel_amenities:
        print(f"  Amenities: {', '.join(place.hotel_amenities[:5])}")
    if reviews_saved is not None:
        print(f"  Reviews:  {reviews_saved:,} saved")


def _progress_bar(done, total, width=30):
    if total == 0:
        return ""
    pct = min(100, int(100 * done / total))
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {done}/{total} ({pct}%)"


def _clear_line():
    sys.stderr.write("\r\033[K")
    sys.stderr.flush()


def _print_phase(label, done, total, extra=""):
    bar = _progress_bar(done, total)
    line = f"  {label:<18} {bar}"
    if extra:
        line += f"  {extra}"
    sys.stderr.write(f"\r{line}")
    sys.stderr.flush()


def _add_common_args(p):
    p.add_argument("--proxy", help="Proxy URL (socks5://... or http://...)")
    p.add_argument("--lang", default="en", help="Language code")
    p.add_argument("--gl", default="us", help="Country code")
    p.add_argument("--delay", type=float, default=2.5, help="Min delay between requests")
    p.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    p.add_argument("--session-file", default="output/session.json", help="Session persistence file")
    p.add_argument("--quiet", "-q", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")


def cmd_search(args):
    _setup_logging(args.verbose)
    db = Database(args.db)
    job_id = args.job_id or hashlib.sha256(args.query.encode()).hexdigest()[:16]

    print(f"Search: {args.query}")
    print(f"Job ID: {job_id}")
    print(f"Workers: {args.workers}")
    if args.max_places is not None:
        print(f"Max places: {args.max_places}")
    else:
        print("Max places: unlimited")
    if args.max_reviews is not None:
        print(f"Max reviews: {args.max_reviews} per place")
    else:
        print("Max reviews: ALL reviews per place (unlimited)")
    print("-" * 60)

    start = time.time()
    with GoogleMapsScraper(
        proxy=args.proxy, lang=args.lang, gl=args.gl,
        min_delay=args.delay, max_delay=args.delay * 2,
        workers=args.workers, session_file=args.session_file,
    ) as scraper:

        def _overall_cb(done, total):
            if not args.quiet:
                _print_phase("Scraping", done, total)

        def _review_cb(done, total, place_name=""):
            if not args.quiet:
                extra = f"  {place_name[:30]}" if place_name else ""
                _print_phase("Scraping reviews", done, total, extra)

        stats = scraper.search_and_scrape(
            db=db, query=args.query, lat=args.lat, lng=args.lng, zoom=args.zoom,
            max_places=args.max_places, max_reviews=args.max_reviews,
            job_id=job_id,
            progress_callback=_overall_cb,
            review_progress_callback=_review_cb,
        )

    if not args.quiet:
        _clear_line()
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s | Places: {stats['places_saved']}/{stats['places_found']} | Reviews: {stats['reviews_saved']:,} | Errors: {stats['errors']}")
    print(f"Database: {args.db}")
    print(f"To resume later: python main.py resume {job_id}")


def cmd_place(args):
    _setup_logging(args.verbose)
    db = Database(args.db)
    
    print(f"Scraping single place: {args.place_id}")
    if args.max_reviews is not None:
        print(f"Max reviews: {args.max_reviews}")
    else:
        print("Max reviews: ALL reviews (unlimited)")
    print("-" * 60)

    start = time.time()
    with GoogleMapsScraper(
        proxy=args.proxy, lang=args.lang, gl=args.gl,
        min_delay=args.delay, max_delay=args.delay * 2,
        workers=args.workers, session_file=args.session_file,
    ) as scraper:
        place, reviews_saved = scraper.scrape_single_place(
            db, args.place_id, 
            max_reviews=args.max_reviews,
            lat=args.lat, lng=args.lng, 
            query=args.query if hasattr(args, 'query') else ""
        )

    if not place:
        print("Failed to fetch place.", file=sys.stderr)
        sys.exit(1)

    _print_place(place, reviews_saved=reviews_saved)
    print(f"\nSaved to {args.db}")
    elapsed = time.time() - start
    print(f"Time: {elapsed:.1f}s")


def cmd_list(args):
    _setup_logging(args.verbose)
    with GoogleMapsScraper(
        proxy=args.proxy, lang=args.lang, gl=args.gl,
        min_delay=args.delay, max_delay=args.delay * 2,
    ) as scraper:
        print(f"Searching: '{args.query}'")
        results = scraper.search(
            query=args.query, lat=args.lat, lng=args.lng,
            zoom=args.zoom, max_results=args.max_places,
        )

    for i, r in enumerate(results, 1):
        cats = ", ".join(r.get("categories", [])[:2])
        rating = r.get("rating") or ""
        line = f"  [{i}] {r.get('name', '?')}"
        if rating:
            line += f"  |  {rating}/5"
        if cats:
            line += f"  |  {cats}"
        print(line)
        print(f"       {r['place_id']}")

    print(f"\nFound {len(results)} place(s).", file=sys.stderr)


def cmd_resume(args):
    _setup_logging(args.verbose)
    db = Database(args.db)
    job = db.get_job(args.job_id)
    if not job:
        print(f"Job not found: {args.job_id}", file=sys.stderr)
        sys.exit(1)

    print(f"Resuming job: {args.job_id}")
    print(f"Query: {job.get('query', 'N/A')}")
    print(f"Progress: {job.get('places_done', 0)}/{job.get('places_total', 0)} places")
    if args.max_reviews is not None:
        print(f"Max reviews: {args.max_reviews} per place")
    else:
        print("Max reviews: ALL reviews per place (unlimited)")
    print("-" * 60)

    start = time.time()
    with GoogleMapsScraper(
        proxy=args.proxy, lang=args.lang, gl=args.gl,
        min_delay=args.delay, max_delay=args.delay * 2,
        workers=args.workers, session_file=args.session_file,
    ) as scraper:
        def _place_cb(done, total):
            if not args.quiet:
                _print_phase("Scraping places", done, total)

        def _review_cb(done, total, place_name=""):
            if not args.quiet:
                extra = f"  {place_name[:30]}" if place_name else ""
                _print_phase("Scraping reviews", done, total, extra)

        stats = scraper.resume_job(
            db, args.job_id, max_reviews=args.max_reviews,
            place_progress_callback=_place_cb,
            review_progress_callback=_review_cb,
        )

    if not args.quiet:
        _clear_line()
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s | Places: {stats['places_saved']}/{stats['places_found']} | Reviews: {stats['reviews_saved']:,} | Errors: {stats['errors']}")


def cmd_stats(args):
    _setup_logging(args.verbose)
    db = Database(args.db)
    stats = db.get_stats()
    print(f"Database: {args.db}")
    print(f"  Places:  {stats['places']}")
    print(f"  Reviews: {stats['reviews']:,}")
    print(f"  Pending: {stats['pending_reviews']} places need reviews")
    
    jobs = db.list_jobs(limit=10)
    if jobs:
        print(f"\nRecent jobs:")
        for job in jobs:
            status_icon = "✓" if job["status"] == "done" else "○" if job["status"] == "running" else "✗"
            print(f"  {status_icon} {job['job_id']} | {job['query'][:40]} | {job['places_done']}/{job['places_total']} places | {job['reviews_done']} reviews | {job['status']}")


def cmd_jobs(args):
    _setup_logging(args.verbose)
    db = Database(args.db)
    jobs = db.list_jobs(limit=args.limit)
    print(f"Recent jobs in {args.db}:")
    print("-" * 80)
    for job in jobs:
        status_icon = "✓" if job["status"] == "done" else "○" if job["status"] == "running" else "✗"
        print(f"{status_icon} {job['job_id']}")
        print(f"  Query:    {job['query']}")
        print(f"  Places:   {job['places_done']}/{job['places_total']}")
        print(f"  Reviews:  {job['reviews_done']}")
        print(f"  Status:   {job['status']}")
        print(f"  Updated:  {job['updated_at']}")
        if job['error']:
            print(f"  Error:    {job['error']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        prog="gmaps-request",
        description="High-scale, request-based Google Maps data extraction.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    sp = subs.add_parser("search", help="Search and scrape all results")
    sp.add_argument("query")
    sp.add_argument("--lat", type=float, default=0.0)
    sp.add_argument("--lng", type=float, default=0.0)
    sp.add_argument("--zoom", type=int, default=13)
    sp.add_argument("--max-places", type=int, default=None, help="Max places to scrape (default: unlimited, 0=skip places)")
    sp.add_argument("--max-reviews", type=int, default=None, help="Max reviews per place (default: unlimited = ALL reviews, 0=skip reviews)")
    sp.add_argument("--db", default="output/gmaps.db")
    sp.add_argument("--job-id", help="Custom job ID for resume tracking")
    _add_common_args(sp)

    pp = subs.add_parser("place", help="Scrape a single place by ID")
    pp.add_argument("place_id")
    pp.add_argument("--lat", type=float, default=0.0)
    pp.add_argument("--lng", type=float, default=0.0)
    pp.add_argument("--max-reviews", type=int, default=None, help="Max reviews (default: unlimited = ALL, 0=skip)")
    pp.add_argument("--db", default="output/gmaps.db")
    _add_common_args(pp)

    lp = subs.add_parser("list", help="List places from search (no scrape)")
    lp.add_argument("query")
    lp.add_argument("--lat", type=float, default=0.0)
    lp.add_argument("--lng", type=float, default=0.0)
    lp.add_argument("--zoom", type=int, default=13)
    lp.add_argument("--max-places", type=int, default=None, help="Max results (default: unlimited)")
    lp.add_argument("--proxy", help="Proxy URL")
    lp.add_argument("--lang", default="en")
    lp.add_argument("--gl", default="us")
    lp.add_argument("--delay", type=float, default=2.5)
    lp.add_argument("--quiet", "-q", action="store_true")
    lp.add_argument("--verbose", "-v", action="store_true")

    rp = subs.add_parser("resume", help="Resume an interrupted job")
    rp.add_argument("job_id")
    rp.add_argument("--max-reviews", type=int, default=None, help="Max reviews per place (default: unlimited = ALL, 0=skip)")
    rp.add_argument("--db", default="output/gmaps.db")
    _add_common_args(rp)

    st = subs.add_parser("stats", help="Show database statistics")
    st.add_argument("--db", default="output/gmaps.db")
    st.add_argument("--quiet", "-q", action="store_true")
    st.add_argument("--verbose", "-v", action="store_true")

    jp = subs.add_parser("jobs", help="List recent jobs")
    jp.add_argument("--db", default="output/gmaps.db")
    jp.add_argument("--limit", type=int, default=20)
    jp.add_argument("--quiet", "-q", action="store_true")
    jp.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    {
        "search": cmd_search,
        "place": cmd_place,
        "list": cmd_list,
        "resume": cmd_resume,
        "stats": cmd_stats,
        "jobs": cmd_jobs,
    }[args.command](args)


if __name__ == "__main__":
    main()
