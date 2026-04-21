import logging

from helpers.client import Client
from helpers.endpoints import search_url, place_url, reviews_url
from helpers.parsers import parse_search_response, parse_place_response, parse_reviews_response

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    def __init__(self, proxy=None, timeout=30, lang="en", gl="us"):
        self.client = Client(proxy=proxy, timeout=timeout)
        self.lang = lang
        self.gl = gl

    def search(self, query, lat=0.0, lng=0.0, zoom=13, max_results=60):
        all_results = []
        page_size = 20
        start = 0

        while len(all_results) < max_results:
            url = search_url(
                query=query, lat=lat, lng=lng, zoom=zoom,
                lang=self.lang, gl=self.gl,
                page_size=page_size, start=start,
            )

            logger.info(f"Searching: q={query}, start={start}")
            resp = self.client.get(url)

            if resp.status_code != 200:
                logger.warning(f"Search returned status {resp.status_code}")
                break

            results = parse_search_response(resp.text)
            if not results:
                break

            all_results.extend(results)
            start += page_size

            if len(results) < page_size:
                break

        return all_results[:max_results]

    def get_place_details(self, place_id, lat=0.0, lng=0.0, query=""):
        url = place_url(
            place_id=place_id, lat=lat, lng=lng, query=query,
            lang=self.lang, gl=self.gl,
        )

        logger.info(f"Getting place details: {place_id}")
        resp = self.client.get(url)

        if resp.status_code != 200:
            logger.warning(f"Place details returned status {resp.status_code}")
            return None

        place = parse_place_response(resp.text)
        if place and not place.place_id:
            place.place_id = place_id
        return place

    def get_reviews(self, place_id, cursor="", page_size=10):
        url = reviews_url(
            place_id=place_id, page_size=page_size, cursor=cursor,
            lang=self.lang, gl=self.gl,
        )

        logger.info(f"Getting reviews: {place_id}, cursor={'start' if not cursor else 'page...'}")
        resp = self.client.get(url)

        if resp.status_code != 200:
            logger.warning(f"Reviews returned status {resp.status_code}")
            return [], None

        return parse_reviews_response(resp.text)

    def iter_reviews(self, place_id, max_reviews=0):
        """Yield reviews one at a time. max_reviews=0 means unlimited."""
        fetched = 0
        cursor = ""

        while True:
            reviews, next_cursor = self.get_reviews(place_id, cursor=cursor)

            for review in reviews:
                yield review
                fetched += 1
                if max_reviews and fetched >= max_reviews:
                    return

            if not next_cursor or not reviews:
                break

            cursor = next_cursor
            logger.info(f"Fetched {fetched} reviews so far")

    def set_delay(self, min_delay, max_delay):
        self.client.set_delay(min_delay, max_delay)

    def set_proxy(self, proxy_url):
        self.client.set_proxy(proxy_url)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
