import logging
import os
import random
import sys
import time
from pathlib import Path

import httpcloak

logger = logging.getLogger(__name__)

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
    """httpcloak Session wrapper tuned for Google Maps.

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
        self._build_session()

    def _build_session(self):
        kwargs = {
            "preset": "chrome-146-windows",
            "timeout": self._timeout,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy

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

    def refresh(self):
        """Reset connections, keep TLS cache"""
        self._session.refresh()
        logger.debug("Session refreshed")

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

    def close(self):
        self.save()
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
