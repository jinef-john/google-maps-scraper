"""Concurrent Google Maps scraper with resume support."""

import hashlib
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from helpers.client import Client
from helpers.endpoints import place_url, reviews_url, search_url
from helpers.parsers import parse_place_response, parse_reviews_response, parse_search_response

logger = logging.getLogger(__name__)


def _print_info(msg):
    """Print user-facing info to stderr (avoids mixing with stdout JSON)."""
    sys.stderr.write(f"  -> {msg}\n")
    sys.stderr.flush()


class GoogleMapsScraper:
    """High-concurrency place scraper using independent httpcloak sessions per worker."""

    def __init__(self, proxy=None, timeout=30, lang="en", gl="us",
                 min_delay=1.0, max_delay=3.0, workers=4, session_file=None):
        self.proxy = proxy
        self.timeout = timeout
        self.lang = lang
        self.gl = gl
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.workers = max(1, workers)
        self.session_file = session_file
        self._main_client = None

    def _new_client(self):
        """Create a fresh client instance."""
        return Client(
            proxy=self.proxy,
            timeout=self.timeout,
            min_delay=self.min_delay,
            max_delay=self.max_delay,
            session_file=self.session_file,
        )

    def start(self):
        self._main_client = self._new_client()
        self._main_client.warmup()

    def stop(self):
        if self._main_client:
            self._main_client.close()
            self._main_client = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # --- Single-shot operations ---

    def search(self, query, lat=0.0, lng=0.0, zoom=13, max_results=None,
               progress_callback=None):
        """Search and return place stubs."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")
        results = []
        page_size = 20
        start = 0
        while max_results is None or len(results) < max_results:
            url = search_url(query=query, lat=lat, lng=lng, zoom=zoom,
                             lang=self.lang, gl=self.gl, page_size=page_size, start=start)
            logger.info("Search: q=%r start=%d", query, start)
            try:
                resp = self._main_client.get(url)
            except Exception as exc:
                logger.error("Search failed at start=%d: %s", start, exc)
                break
            if resp.status_code != 200:
                logger.warning("Search HTTP %d", resp.status_code)
                break
            batch = parse_search_response(resp.text)
            if not batch:
                break
            results.extend(batch)
            start += page_size
            if progress_callback:
                progress_callback(len(results), max_results if max_results is not None else len(results) + page_size)
            if len(batch) < page_size:
                break
        return results[:max_results] if max_results is not None else results

    def get_place(self, place_id, lat=0.0, lng=0.0, query=""):
        """Fetch full details for a single place."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")
        url = place_url(place_id=place_id, lat=lat, lng=lng, query=query,
                        lang=self.lang, gl=self.gl)
        logger.info("Place details: %s", place_id)
        try:
            resp = self._main_client.get(url)
        except Exception as exc:
            logger.error("Place fetch failed %s: %s", place_id, exc)
            return None
        if resp.status_code != 200:
            logger.warning("Place HTTP %d", resp.status_code)
            return None
        place = parse_place_response(resp.text)
        if place and not place.place_id:
            place.place_id = place_id
        return place

    def get_reviews(self, place_id, cursor="", page_size=10):
        """Fetch one page of reviews. Returns (reviews, next_cursor)."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")
        url = reviews_url(place_id=place_id, page_size=page_size, cursor=cursor,
                         lang=self.lang, gl=self.gl)
        logger.info("Reviews: %s cursor=%s", place_id, cursor[:20] if cursor else "start")
        try:
            resp = self._main_client.get(url)
        except Exception as exc:
            logger.error("Reviews failed %s: %s", place_id, exc)
            return [], None
        if resp.status_code != 200:
            logger.warning("Reviews HTTP %d", resp.status_code)
            return [], None
        return parse_reviews_response(resp.text)

    def iter_reviews(self, place_id, max_reviews=None, cursor=""):
        """Yield reviews with resumable cursor support.
        
        If max_reviews is None, yields ALL reviews until exhausted.
        """
        fetched = 0
        while True:
            reviews, next_cursor = self.get_reviews(place_id, cursor=cursor)
            for review in reviews:
                yield review
                fetched += 1
                if max_reviews is not None and fetched >= max_reviews:
                    return
            if not next_cursor or not reviews:
                break
            cursor = next_cursor
            logger.info("  %s: %d reviews so far", place_id, fetched)

    def set_delay(self, min_delay, max_delay):
        self.min_delay = min_delay
        self.max_delay = max_delay
        if self._main_client:
            self._main_client.set_delay(min_delay, max_delay)

    # --- Concurrent batch scraping with resume support ---

    def search_and_scrape(self, db, query, lat=0.0, lng=0.0, zoom=13,
                          max_places=None, max_reviews=None, job_id=None,
                          progress_callback=None,
                          review_progress_callback=None):
        """Search and concurrently scrape details + reviews as results arrive."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")

        job_id = job_id or hashlib.sha256(query.encode()).hexdigest()[:16]
        db.create_job(job_id, query)

        _print_info(f"Searching places: '{query}'")

        # Create independent client instances for each worker
        clients = [self._new_client() for _ in range(self.workers)]
        _print_info("Warming up workers...")
        for c in clients:
            c.warmup()

        stats = {"places_found": 0, "places_saved": 0,
                 "reviews_saved": 0, "errors": 0}
        lock = threading.Lock()
        futures = set()
        client_idx = 0

        def _submit_stub(stub):
            nonlocal client_idx
            cli = clients[client_idx % self.workers]
            client_idx += 1
            fut = exe.submit(self._scrape_one, cli, db, stub, max_reviews, job_id,
                            review_progress_callback)
            futures.add(fut)
            return fut

        def _drain_done():
            done = [f for f in futures if f.done()]
            for f in done:
                futures.remove(f)
                try:
                    place, rc = f.result()
                    with lock:
                        stats["places_saved"] += 1 if place else 0
                        stats["reviews_saved"] += rc
                except Exception as exc:
                    with lock:
                        stats["errors"] += 1
                    logger.error("Worker failed: %s", exc)

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as exe:
                page_size = 20
                start = 0

                while True:
                    url = search_url(query=query, lat=lat, lng=lng, zoom=zoom,
                                     lang=self.lang, gl=self.gl, page_size=page_size, start=start)
                    logger.info("Search: q=%r start=%d", query, start)
                    try:
                        resp = self._main_client.get(url)
                    except Exception as exc:
                        logger.error("Search failed at start=%d: %s", start, exc)
                        break
                    if resp.status_code != 200:
                        logger.warning("Search HTTP %d", resp.status_code)
                        break

                    batch = parse_search_response(resp.text)
                    if not batch:
                        break

                    # Respect max_places limit
                    remaining = max_places - stats["places_found"] if max_places is not None else len(batch)
                    remaining = max(0, remaining)
                    stubs_to_scrape = batch[:remaining]

                    # Persist search stubs so they can be resumed
                    db.add_job_places(job_id, [s["place_id"] for s in stubs_to_scrape])

                    with lock:
                        stats["places_found"] += len(stubs_to_scrape)

                    for stub in stubs_to_scrape:
                        _submit_stub(stub)
                        _drain_done()

                    if progress_callback:
                        progress_callback(stats["places_saved"], stats["places_found"])

                    start += page_size
                    if len(batch) < page_size:
                        break
                    if max_places is not None and stats["places_found"] >= max_places:
                        break

                # Wait for remaining futures
                for fut in as_completed(futures):
                    try:
                        place, rc = fut.result()
                        with lock:
                            stats["places_saved"] += 1 if place else 0
                            stats["reviews_saved"] += rc
                    except Exception as exc:
                        with lock:
                            stats["errors"] += 1
                        logger.error("Worker failed: %s", exc)
                    if progress_callback:
                        progress_callback(stats["places_saved"], stats["places_found"])

        finally:
            for c in clients:
                c.close()

        db.update_job_status(job_id, "done")
        return stats

    def resume_job(self, db, job_id, max_reviews=None,
                   place_progress_callback=None,
                   review_progress_callback=None):
        """Resume an interrupted job."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")

        db.update_job_status(job_id, "running")
        # Re-open done places if we now want more reviews than before
        reopened = db.reopen_job_places_for_reviews(job_id, max_reviews)
        if reopened:
            _print_info(f"Re-opened {reopened} place(s) for more reviews")
        pending = db.get_pending_job_places(job_id)
        if not pending:
            db.update_job_status(job_id, "done")
            return {"places_found": 0, "places_saved": 0, "reviews_saved": 0,
                    "errors": 0, "message": "Nothing to resume"}

        _print_info(f"Resuming job '{job_id}' with {len(pending)} pending place(s)..")
        stats = {"places_found": len(pending), "places_saved": 0,
                 "reviews_saved": 0, "errors": 0}

        clients = [self._new_client() for _ in range(self.workers)]
        for c in clients:
            c.warmup()

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as exe:
                futures = {}
                for idx, item in enumerate(pending):
                    cli = clients[idx % self.workers]
                    stub = {
                        "place_id": item["place_id"],
                        "name": item["name"],
                        "lat": 0.0, "lng": 0.0,
                        "cursor": item.get("cursor", ""),
                    }
                    fut = exe.submit(self._scrape_one, cli, db, stub, max_reviews, job_id,
                                     review_progress_callback)
                    futures[fut] = stub

                for fut in as_completed(futures):
                    stub = futures[fut]
                    try:
                        place, reviews_count = fut.result()
                        stats["places_saved"] += 1 if place else 0
                        stats["reviews_saved"] += reviews_count
                    except Exception as exc:
                        stats["errors"] += 1
                        logger.error("Failed %s: %s", stub["place_id"], exc)
                        db.mark_job_place_done(job_id, stub["place_id"], 0)

                    if place_progress_callback:
                        place_progress_callback(stats["places_saved"], stats["places_found"])

        finally:
            for c in clients:
                c.close()

        db.update_job_status(job_id, "done")
        return stats

    def scrape_places(self, db, place_ids, max_reviews=None, job_id=None,
                      place_progress_callback=None,
                      review_progress_callback=None):
        """Scrape details + reviews for known place IDs."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")

        job_id = job_id or hashlib.sha256((",".join(place_ids)).encode()).hexdigest()[:16]
        db.create_job(job_id, f"batch:{len(place_ids)} places")
        db.add_job_places(job_id, place_ids)

        pending = db.get_pending_job_places(job_id)
        stats = {"places_found": len(place_ids), "places_saved": 0,
                 "reviews_saved": 0, "errors": 0}

        clients = [self._new_client() for _ in range(self.workers)]
        for c in clients:
            c.warmup()

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as exe:
                futures = {}
                for idx, item in enumerate(pending):
                    cli = clients[idx % self.workers]
                    stub = {
                        "place_id": item["place_id"],
                        "name": item["name"],
                        "lat": 0.0, "lng": 0.0,
                        "cursor": item.get("cursor", ""),
                    }
                    fut = exe.submit(self._scrape_one, cli, db, stub, max_reviews, job_id,
                                     review_progress_callback)
                    futures[fut] = stub

                for fut in as_completed(futures):
                    stub = futures[fut]
                    try:
                        place, rc = fut.result()
                        stats["places_saved"] += 1 if place else 0
                        stats["reviews_saved"] += rc
                    except Exception as exc:
                        stats["errors"] += 1
                        logger.error("Failed %s: %s", stub["place_id"], exc)
                        db.mark_job_place_done(job_id, stub["place_id"], 0)

                    if place_progress_callback:
                        place_progress_callback(stats["places_saved"], stats["places_found"])

        finally:
            for c in clients:
                c.close()

        db.update_job_status(job_id, "done")
        return stats

    def scrape_single_place(self, db, place_id, max_reviews=None, lat=0.0, lng=0.0, query=""):
        """Scrape a single place with full details and reviews."""
        if not self._main_client:
            raise RuntimeError("Scraper not started")

        _print_info(f"Fetching place details for {place_id[:30]}...")
        place = self.get_place(place_id, lat=lat, lng=lng, query=query)
        if not place:
            _print_info(f"Failed to fetch place details for {place_id[:30]}")
            return None, 0

        db.upsert_place(place)
        _print_info(f"Saved place: {place.name} ({place.rating}/5, {place.review_count:,} reviews)")

        reviews_saved = 0
        cursor = ""
        if max_reviews != 0:
            # Resume from DB cursor if we already have reviews
            existing = db.get_place_cursor(place_id)
            rcursor = existing.get("cursor", "")
            already_saved = existing.get("total_saved", 0)

            if already_saved and max_reviews is not None:
                remaining = max(0, max_reviews - already_saved)
                if remaining == 0:
                    _print_info(f"Already has {already_saved} reviews — skipping")
                    return place, 0
                target = remaining
                _print_info(f"Scraping reviews for: {place.name} (resuming from {already_saved}, fetching up to {remaining} more)")
            else:
                target = max_reviews
                _print_info(f"Scraping reviews for: {place.name}")

            while True:
                rurl = reviews_url(place_id, page_size=10, cursor=rcursor,
                                   lang=self.lang, gl=self.gl)
                try:
                    rresp = self._main_client.get(rurl)
                except Exception:
                    break
                if rresp.status_code != 200:
                    break
                reviews, next_cursor = parse_reviews_response(rresp.text)
                for review in reviews:
                    db.insert_review(place_id, review)
                    reviews_saved += 1
                    if target is not None and reviews_saved >= target:
                        break
                if target is not None and reviews_saved >= target:
                    break
                if not next_cursor or not reviews:
                    break
                rcursor = next_cursor
                total_so_far = already_saved + reviews_saved
                if total_so_far % 50 == 0:
                    _print_info(f"  ... {total_so_far} reviews scraped for {place.name}")

            total_reviews = already_saved + reviews_saved
            # Only mark as fetched if we got reviews or place has none
            if total_reviews > 0 or place.review_count == 0:
                db.mark_reviews_fetched(place_id, rcursor, total_reviews)
            cursor = rcursor
            _print_info(f"Total reviews saved for {place.name}: {total_reviews} (+{reviews_saved} new)")

        return place, reviews_saved

    def _scrape_one(self, client, db, stub, max_reviews, job_id,
                    review_progress_callback=None):
        """Scrape a single place using the given client (internal, for workers)."""
        pid = stub["place_id"]
        lat = stub.get("lat", 0.0)
        lng = stub.get("lng", 0.0)
        place_name = stub.get("name", "")

        url = place_url(pid, lat, lng, lang=self.lang, gl=self.gl)
        try:
            resp = client.get(url)
        except Exception as exc:
            logger.warning("Place fetch failed %s: %s", pid, exc)
            db.mark_job_place_done(job_id, pid, 0)
            return None, 0

        if resp.status_code != 200:
            db.mark_job_place_done(job_id, pid, 0)
            return None, 0

        place = parse_place_response(resp.text)
        if not place:
            db.mark_job_place_done(job_id, pid, 0)
            return None, 0
        if not place.place_id:
            place.place_id = pid

        db.upsert_place(place)

        reviews_saved = 0
        cursor = stub.get("cursor", "")
        if max_reviews != 0:
            rcursor = cursor
            retries = 0
            while True:
                rurl = reviews_url(pid, page_size=10, cursor=rcursor,
                                   lang=self.lang, gl=self.gl)
                try:
                    rresp = client.get(rurl)
                except Exception:
                    break
                if rresp.status_code != 200:
                    break
                reviews, next_cursor = parse_reviews_response(rresp.text)

                # If we got 0 reviews but the place is known to have reviews,
                # the session may have expired. Refresh once and retry.
                if not reviews and place.review_count > 0 and retries == 0:
                    logger.warning("Reviews empty for %s (has %d reviews) — refreshing session...", pid, place.review_count)
                    try:
                        client.save()
                        client.refresh()
                        rresp = client.get(rurl)
                        reviews, next_cursor = parse_reviews_response(rresp.text)
                    except Exception as exc:
                        logger.debug("Session refresh failed: %s", exc)
                    retries += 1
                    continue

                for review in reviews:
                    db.insert_review(pid, review)
                    reviews_saved += 1
                    if max_reviews is not None and reviews_saved >= max_reviews:
                        break
                    if review_progress_callback:
                        review_progress_callback(reviews_saved, max_reviews if max_reviews is not None else reviews_saved + 10, place_name)
                if max_reviews is not None and reviews_saved >= max_reviews:
                    break
                if not next_cursor or not reviews:
                    break
                rcursor = next_cursor

            # Only mark reviews as fetched if we actually got some, or if the
            # place genuinely has no reviews. If review_count > 0 but we saved 0,
            # the endpoint likely failed — leave it unfetched so resume can retry.
            if reviews_saved > 0 or place.review_count == 0:
                db.mark_reviews_fetched(pid, rcursor, reviews_saved)
            cursor = rcursor

        db.mark_job_place_done(job_id, pid, reviews_saved, cursor)
        return place, reviews_saved
