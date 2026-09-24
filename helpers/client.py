import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import httpcloak

from helpers.endpoints import BASE, place_page_url
from helpers.utils import _decode_key

logger = logging.getLogger(__name__)

_KEI_RE = re.compile(r"kEI=.([A-Za-z0-9_\-]+).")


_BATCHEXECUTE_HEADERS = {
    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "x-same-domain": "1",
    "origin": "https://www.google.com",
    "x-maps-bgkey": _decode_key("HMYYL"),
}

_MAPS_HEADERS = {
    "accept": "*/*",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-browser-channel": "stable",
    "x-browser-year": "2026",
    "x-maps-diversion-context-bin": "CAE=",
}

_WARMUP_URLS = [
    "https://www.google.com",
    "https://www.google.com/maps",
    "https://www.google.com/maps/place/Harvard+University/@42.3770029,-71.1188488,15z",
]


class Client:
    """Session wrapper

    Features:
    - warmup() before first request (simulates real user)
    - retry with exponential backoff + refresh on 429
    - save/load session for 0-RTT resumption across runs
    """

    def __init__(self, proxy=None, timeout=30, min_delay=1.0, max_delay=3.0, session_file=None):
        self._proxy = proxy
        self._timeout = timeout
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._session_file = session_file
        self._req_count = 0
        self._warmup_done = False
        self._session = None
        self._review_sessions = {}
        self._build_session()

    def _session_kwargs(self):
        kwargs = {
            "preset": "chrome-146-windows",
            "timeout": self._timeout,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy
        return kwargs

    def _build_session(self):
        kwargs = self._session_kwargs()

        if self._session_file and os.path.exists(self._session_file):
            try:
                self._session = httpcloak.Session.load(self._session_file)
                logger.debug("Loaded session from %s", self._session_file)
                return
            except Exception as exc:
                logger.warning("Failed to load session: %s", exc)

        self._session = httpcloak.Session(**kwargs)

    def warmup(self):
        """Simulate a real user visiting Google Maps."""
        if self._warmup_done:
            return
        sys.stderr.write("  -> Warming up session...")
        sys.stderr.flush()
        for url in _WARMUP_URLS:
            try:
                self._session.get(url)
            except Exception as exc:
                logger.debug("Warmup failed for %s: %s", url, exc)
        self._warmup_done = True
        sys.stderr.write(" done\n")
        sys.stderr.flush()
        logger.debug("Warmup complete")

    def get(self, url, extra_headers=None):
        """GET with Maps headers, throttling, and retry logic."""
        if not self._warmup_done:
            self.warmup()

        headers = dict(_MAPS_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        self._throttle()

        last_err = None
        for attempt in range(1, 4):
            try:
                resp = self._session.get(url, headers=headers)
                self._req_count += 1

                if resp.status_code == 429:
                    backoff = min(2 ** attempt + random.random(), 30)
                    logger.warning("Rate limited (429). Backoff %.1fs (attempt %d/3)", backoff, attempt)
                    time.sleep(backoff)
                    self._session.refresh()
                    continue

                return resp

            except Exception as exc:
                last_err = exc
                wait = min(2 ** attempt, 10)
                logger.debug("Attempt %d/3 failed: %s. Retrying in %.1fs", attempt, exc, wait)
                time.sleep(wait)

        raise last_err or RuntimeError("Request failed after 3 attempts")

    def post(self, url, data, extra_headers=None):
        """POST with Maps + batchexecute headers, throttling, and retry logic."""
        if not self._warmup_done:
            self.warmup()

        headers = dict(_MAPS_HEADERS)
        headers.update(_BATCHEXECUTE_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        self._throttle()

        last_err = None
        for attempt in range(1, 4):
            try:
                resp = self._session.post(url, data=data, headers=headers)
                self._req_count += 1

                if resp.status_code == 429:
                    backoff = min(2 ** attempt + random.random(), 30)
                    logger.warning("Rate limited (429). Backoff %.1fs (attempt %d/3)", backoff, attempt)
                    time.sleep(backoff)
                    self._session.refresh()
                    continue

                return resp

            except Exception as exc:
                last_err = exc
                wait = min(2 ** attempt, 10)
                logger.debug("Attempt %d/3 failed: %s. Retrying in %.1fs", attempt, exc, wait)
                time.sleep(wait)

        raise last_err or RuntimeError("Request failed after 3 attempts")

    def get_review_session(self, place_id, lat=0.0, lng=0.0, query="", force=False):
        """Visit the place's /maps/place page to harvest a fresh kEI token.

        Reviews (MapsUgcPostService.ListUgcPosts) require an ei token pulled
        from a real page load; returns (ei, source_path) for use in
        reviews_batchexecute_request(), or (None, source_path) on failure.
        Cached per place_id so pagination doesn't re-fetch the page each time.
        """
        if not force and place_id in self._review_sessions:
            return self._review_sessions[place_id]

        source_path = place_page_url(place_id, lat, lng, query=query).replace(BASE, "", 1)
        resp = self.get(BASE + source_path)
        m = _KEI_RE.search(resp.text) if resp.status_code == 200 else None
        result = (m.group(1) if m else None), source_path
        self._review_sessions[place_id] = result
        return result

    def refresh(self):
        """Reset connections, keep TLS cache"""
        self._session.refresh()
        logger.debug("Session refreshed")

    def reset(self):
        """Start over with a brand-new session (fresh cookies) and re-warm on next request."""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = httpcloak.Session(**self._session_kwargs())
        self._warmup_done = False
        self._review_sessions.clear()
        logger.debug("Session reset")

    def save(self):
        """Persist session for 0-RTT resumption."""
        if self._session_file:
            Path(self._session_file).parent.mkdir(parents=True, exist_ok=True)
            try:
                self._session.save(self._session_file)
            except Exception as exc:
                logger.debug("Session save failed: %s", exc)

    def set_proxy(self, proxy_url):
        """Switch proxy mid-session."""
        self._session.set_proxy(proxy_url)
        self._proxy = proxy_url

    def set_delay(self, min_delay, max_delay):
        self._min_delay = min_delay
        self._max_delay = max_delay

    def _throttle(self):
        if self._req_count > 0:
            time.sleep(random.uniform(self._min_delay, self._max_delay))

    def fetch(self, url, headers=None):
        """Generic GET without Maps-specific headers.
        """
        headers = dict(headers) if headers else {}
        self._throttle()
        last_err = None
        for attempt in range(1, 4):
            try:
                resp = self._session.get(url, headers=headers, timeout=self._timeout)
                self._req_count += 1
                if resp.status_code == 429:
                    backoff = min(2 ** attempt + random.random(), 30)
                    logger.warning("Rate limited (429) on %s. Backoff %.1fs (attempt %d/3)", url, backoff, attempt)
                    time.sleep(backoff)
                    self._session.refresh()
                    continue
                return resp
            except Exception as exc:
                last_err = exc
                wait = min(2 ** attempt, 10)
                logger.debug("Attempt %d/3 failed for %s: %s. Retrying in %.1fs", attempt, url, exc, wait)
                time.sleep(wait)
        raise last_err or RuntimeError("Request failed after 3 attempts")

    def close(self):
        self.save()
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
