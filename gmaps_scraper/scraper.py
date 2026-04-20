"""Main scraper orchestrator that ties together client, endpoints, and parsers."""

import logging

from .client import Client
from .endpoints import search_url, place_url, reviews_url
from .parsers import parse_search_response, parse_place_response, parse_reviews_response
from .models import Place

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    """High-level scraper for Google Maps place data.

    Usage:
        with GoogleMapsScraper() as scraper:
            results = scraper.search("hospitals in Nairobi", lat=-1.286, lng=36.817)
            for place_summary in results:
                place = scraper.get_place_details(place_summary["place_id"],
                                                  place_summary["lat"],
                                                  place_summary["lng"])
                reviews = scraper.get_all_reviews(place_summary["place_id"])
                place.reviews = reviews
                print(place.to_dict())
    """

    def __init__(self, proxy=None, timeout=30, lang="en", gl="us"):
        """Initialize the scraper.

        Args:
            proxy: Optional proxy URL (socks5://..., http://...)
            timeout: Request timeout in seconds
            lang: Language code for results
            gl: Country/region code
        """
        self.client = Client(proxy=proxy, timeout=timeout)
        self.lang = lang
        self.gl = gl

    def search(self, query, lat=0.0, lng=0.0, zoom=13, max_results=60):
        """Search for places matching a query.

        Args:
            query: Search string (e.g. "web developers in bangalore")
            lat: Search center latitude (0 for auto/worldwide)
            lng: Search center longitude
            zoom: Map zoom level (affects search radius)
            max_results: Maximum number of results to fetch (paginated)

        Returns:
            List of place summaries: [{place_id, name, lat, lng, rating, categories}]
        """
        all_results = []
        page_size = 20
        start = 0

        while len(all_results) < max_results:
            url = search_url(
                query=query,
                lat=lat,
                lng=lng,
                zoom=zoom,
                lang=self.lang,
                gl=self.gl,
                page_size=page_size,
                start=start,
            )

            logger.info(f"Searching: q={query}, start={start}")
            resp = self.client.get(url)

            if resp.status_code != 200:
                logger.warning(f"Search returned status {resp.status_code}")
                break

            results = parse_search_response(resp.text)
            if not results:
                logger.info("No more search results")
                break

            all_results.extend(results)
            start += page_size

            if len(results) < page_size:
                break

        return all_results[:max_results]

    def get_place_details(self, place_id, lat=0.0, lng=0.0, query=""):
        """Get full details for a single place.

        Args:
            place_id: The hex place ID (e.g. "0x182f17eb1d447363:0x17a2d29bdcf01fda")
            lat: Place latitude
            lng: Place longitude
            query: Original search query for context

        Returns:
            Place object with all available details
        """
        url = place_url(
            place_id=place_id,
            lat=lat,
            lng=lng,
            query=query,
            lang=self.lang,
            gl=self.gl,
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
        """Get a single page of reviews for a place.

        Args:
            place_id: The hex place ID
            cursor: Pagination cursor (empty for first page)
            page_size: Number of reviews per page

        Returns:
            tuple: (list of Review objects, next_cursor or None)
        """
        url = reviews_url(
            place_id=place_id,
            page_size=page_size,
            cursor=cursor,
            lang=self.lang,
            gl=self.gl,
        )

        logger.info(f"Getting reviews: {place_id}, cursor={'start' if not cursor else 'page...'}")
        resp = self.client.get(url)

        if resp.status_code != 200:
            logger.warning(f"Reviews returned status {resp.status_code}")
            return [], None

        return parse_reviews_response(resp.text)

    def get_all_reviews(self, place_id, max_reviews=100):
        """Get all reviews for a place (paginated).

        Args:
            place_id: The hex place ID
            max_reviews: Maximum number of reviews to fetch

        Returns:
            List of Review objects
        """
        all_reviews = []
        cursor = ""

        while len(all_reviews) < max_reviews:
            reviews, next_cursor = self.get_reviews(place_id, cursor=cursor)

            if not reviews:
                break

            all_reviews.extend(reviews)
            logger.info(f"Fetched {len(all_reviews)} reviews so far")

            if not next_cursor:
                break

            cursor = next_cursor

        return all_reviews[:max_reviews]

    def scrape_place(self, place_id, lat=0.0, lng=0.0, query="", max_reviews=100):
        """Scrape everything about a place: details + all reviews.

        Args:
            place_id: The hex place ID
            lat: Place latitude
            lng: Place longitude
            query: Original search query
            max_reviews: Max reviews to fetch

        Returns:
            Place object with reviews populated, or None on failure
        """
        place = self.get_place_details(place_id, lat, lng, query)
        if not place:
            return None

        reviews = self.get_all_reviews(place_id, max_reviews=max_reviews)
        place.reviews = reviews
        return place

    def search_and_scrape(self, query, lat=0.0, lng=0.0, zoom=13,
                          max_places=20, max_reviews_per_place=50):
        """Full pipeline: search for places then scrape each one.

        Args:
            query: Search string
            lat: Search center latitude
            lng: Search center longitude
            zoom: Map zoom level
            max_places: Maximum number of places to scrape
            max_reviews_per_place: Max reviews per place

        Yields:
            Place objects (with reviews) one at a time
        """
        results = self.search(query, lat=lat, lng=lng, zoom=zoom, max_results=max_places)
        logger.info(f"Found {len(results)} places for '{query}'")

        for i, result in enumerate(results):
            logger.info(f"Scraping place {i+1}/{len(results)}: {result.get('name', 'unknown')}")
            place = self.scrape_place(
                place_id=result["place_id"],
                lat=result.get("lat", lat),
                lng=result.get("lng", lng),
                query=query,
                max_reviews=max_reviews_per_place,
            )
            if place:
                yield place

    def set_delay(self, min_delay, max_delay):
        """Configure request throttling.

        Args:
            min_delay: Minimum seconds between requests
            max_delay: Maximum seconds between requests
        """
        self.client.set_delay(min_delay, max_delay)

    def set_proxy(self, proxy_url):
        """Switch proxy mid-session."""
        self.client.set_proxy(proxy_url)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
