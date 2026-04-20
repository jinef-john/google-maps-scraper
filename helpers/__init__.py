"""Helper functions for HAR analysis and response validation."""

import json


def load_har_entries(har_path, url_filter=None):
    """Load HAR file and optionally filter entries by URL pattern.

    Args:
        har_path: Path to the HAR file
        url_filter: Optional string to filter URLs (e.g. "listugcposts")

    Returns:
        List of (url, response_text) tuples
    """
    with open(har_path, "r") as f:
        har = json.load(f)

    results = []
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        if url_filter and url_filter not in url:
            continue
        text = entry["response"]["content"].get("text", "")
        if text:
            results.append((url, text))

    return results


def extract_search_queries(har_path):
    """Extract all search queries from a HAR file.

    Returns list of unique query strings.
    """
    from urllib.parse import unquote

    with open(har_path, "r") as f:
        har = json.load(f)

    queries = set()
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        if "tbm=map" in url or "/maps/preview/place" in url:
            if "&q=" in url:
                q = url.split("&q=")[1].split("&")[0]
                decoded = unquote(q).replace("+", " ")
                if len(decoded) > 3:
                    queries.add(decoded)

    return sorted(queries)


def get_request_headers(har_path, url_filter="maps/preview/place"):
    """Extract request headers for a specific endpoint from HAR.

    Useful for seeing what headers Google expects.
    """
    with open(har_path, "r") as f:
        har = json.load(f)

    for entry in har["log"]["entries"]:
        if url_filter in entry["request"]["url"]:
            headers = {}
            for h in entry["request"]["headers"]:
                name = h["name"]
                if not name.startswith(":"):
                    headers[name] = h["value"]
            return headers

    return {}


def validate_response(text):
    """Check if a response looks like a valid Google Maps API response.

    Returns (is_valid, error_message)
    """
    if not text:
        return False, "Empty response"

    if text.startswith(")]}'"):
        text = text[4:].strip()

    # Check if it's wrapped JSON
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if "d" in data:
                return True, None
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

    # Check if it's a raw array
    if text.startswith("["):
        try:
            json.loads(text)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON array: {e}"

    return False, f"Unexpected response format: {text[:50]}"
