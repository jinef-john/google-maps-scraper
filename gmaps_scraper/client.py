"""HTTP client wrapper using httpcloak for Google Maps scraping."""

import time
import random
import httpcloak


MAPS_HEADERS = {
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "x-maps-diversion-context-bin": "CAE=",
    "accept": "*/*",
    "x-browser-channel": "stable",
    "x-browser-year": "2026",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://www.google.com/",
    "accept-language": "en-US,en;q=0.9",
}


class Client:
    """Manages httpcloak session for Google Maps requests."""

    def __init__(self, proxy=None, timeout=30):
        kwargs = {
            "preset": "chrome-146-windows",
            "timeout": timeout,
        }
        if proxy:
            kwargs["proxy"] = proxy

        self.session = httpcloak.Session(**kwargs)
        self._warmup_done = False
        self._request_count = 0
        self._min_delay = 1.0
        self._max_delay = 3.0

    def warmup(self):
        """Warm up TLS session by visiting google.com first."""
        self.session.get("https://www.google.com")
        self._warmup_done = True

    def get(self, url, extra_headers=None):
        """Make a GET request with Maps headers and throttling."""
        if not self._warmup_done:
            self.warmup()

        headers = dict(MAPS_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        self._throttle()
        resp = self.session.get(url, headers=headers)
        self._request_count += 1
        return resp

    def set_proxy(self, proxy_url):
        """Switch proxy mid-session."""
        self.session.set_proxy(proxy_url)

    def _throttle(self):
        """Random delay between requests to avoid rate limiting."""
        if self._request_count > 0:
            delay = random.uniform(self._min_delay, self._max_delay)
            time.sleep(delay)

    def set_delay(self, min_delay, max_delay):
        """Configure throttle delay range in seconds."""
        self._min_delay = min_delay
        self._max_delay = max_delay

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
