"""Utility functions for the Google Maps scraper."""

import json
import re


def extract_place_id_from_url(url):
    """Extract a place ID from a Google Maps URL.

    Supports formats:
        - 0x182f17eb1d447363:0x17a2d29bdcf01fda (hex format)
        - ChIJ... (base64-like feature ID)
    """
    hex_match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    if hex_match:
        return hex_match.group(1)

    feat_match = re.search(r"(ChIJ[A-Za-z0-9_-]+)", url)
    if feat_match:
        return feat_match.group(1)

    return None


def coords_from_query(query):
    """Try to infer approximate lat/lng from common city names in a query.

    Returns (lat, lng) or (0, 0) if unknown.
    """
    cities = {
        "nairobi": (-1.2864, 36.8172),
        "bangalore": (12.9716, 77.5946),
        "bengaluru": (12.9716, 77.5946),
        "mumbai": (19.0760, 72.8777),
        "delhi": (28.6139, 77.2090),
        "new york": (40.7128, -74.0060),
        "london": (51.5074, -0.1278),
        "paris": (48.8566, 2.3522),
        "tokyo": (35.6762, 139.6503),
        "sydney": (-33.8688, 151.2093),
        "dubai": (25.2048, 55.2708),
        "singapore": (1.3521, 103.8198),
        "los angeles": (34.0522, -118.2437),
        "san francisco": (37.7749, -122.4194),
        "chicago": (41.8781, -87.6298),
        "toronto": (43.6532, -79.3832),
        "lagos": (6.5244, 3.3792),
        "cairo": (30.0444, 31.2357),
        "johannesburg": (-26.2041, 28.0473),
        "cape town": (-33.9249, 18.4241),
    }

    query_lower = query.lower()
    for city, coords in cities.items():
        if city in query_lower:
            return coords

    return (0.0, 0.0)


def parse_har_for_cookies(har_path):
    """Extract Google cookies from a HAR file for session bootstrap.

    Args:
        har_path: Path to the HAR file

    Returns:
        dict of cookie name -> value
    """
    with open(har_path, "r") as f:
        har = json.load(f)

    cookies = {}
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        if "google.com" in url:
            for header in entry["request"]["headers"]:
                if header["name"].lower() == "cookie":
                    for part in header["value"].split(";"):
                        part = part.strip()
                        if "=" in part:
                            name, _, value = part.partition("=")
                            cookies[name.strip()] = value.strip()
                    return cookies
    return cookies


def format_place_summary(place_dict, index=None):
    """Format a place dict as a readable summary string."""
    prefix = f"[{index}] " if index else ""
    name = place_dict.get("name", "Unknown")
    rating = place_dict.get("rating", 0)
    review_count = place_dict.get("review_count", 0)
    address = place_dict.get("address", "")
    categories = ", ".join(place_dict.get("categories", [])[:3])

    lines = [f"{prefix}{name}", f"    Rating: {rating}/5 ({review_count} reviews)"]
    if categories:
        lines.append(f"    Type: {categories}")
    if address:
        lines.append(f"    Address: {address}")
    if place_dict.get("website"):
        lines.append(f"    Web: {place_dict['website']}")
    if place_dict.get("phone"):
        lines.append(f"    Phone: {place_dict['phone']}")

    return "\n".join(lines)
