"""Helper utilities."""

import re


def extract_place_id_from_url(url):
    """Extract a place ID from a Google Maps URL."""
    hex_match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    if hex_match:
        return hex_match.group(1)
    feat_match = re.search(r"(ChIJ[A-Za-z0-9_-]+)", url)
    if feat_match:
        return feat_match.group(1)
    return None


def coords_from_query(query):
    """Infer approximate lat/lng from common city names."""
    cities = {
        "nairobi": (-1.2864, 36.8172), "bangalore": (12.9716, 77.5946),
        "bengaluru": (12.9716, 77.5946), "mumbai": (19.0760, 72.8777),
        "delhi": (28.6139, 77.2090), "new york": (40.7128, -74.0060),
        "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
        "tokyo": (35.6762, 139.6503), "sydney": (-33.8688, 151.2093),
        "dubai": (25.2048, 55.2708), "singapore": (1.3521, 103.8198),
        "los angeles": (34.0522, -118.2437), "san francisco": (37.7749, -122.4194),
        "chicago": (41.8781, -87.6298), "toronto": (43.6532, -79.3832),
        "lagos": (6.5244, 3.3792), "cairo": (30.0444, 31.2357),
        "johannesburg": (-26.2041, 28.0473), "cape town": (-33.9249, 18.4241),
        "berlin": (52.5200, 13.4050), "madrid": (40.4168, -3.7038),
        "rome": (41.9028, 12.4964), "amsterdam": (52.3676, 4.9041),
        "barcelona": (41.3851, 2.1734), "istanbul": (41.0082, 28.9784),
        "moscow": (55.7558, 37.6173), "beijing": (39.9042, 116.4074),
        "shanghai": (31.2304, 121.4737), "hong kong": (22.3193, 114.1694),
        "seoul": (37.5665, 126.9780), "mexico city": (19.4326, -99.1332),
        "sao paulo": (-23.5505, -46.6333), "buenos aires": (-34.6037, -58.3816),
        "mumbai": (19.0760, 72.8777), "jakarta": (-6.2088, 106.8456),
        "bangkok": (13.7563, 100.5018), "kuala lumpur": (3.1390, 101.6869),
        "manila": (14.5995, 120.9842), "ho chi minh": (10.8231, 106.6297),
    }
    q = query.lower()
    for city, coords in cities.items():
        if city in q:
            return coords
    return (0.0, 0.0)


def format_place_summary(place_dict, index=None):
    """Format a place dict as a readable summary string."""
    prefix = f"[{index}] " if index else ""
    name = place_dict.get("name", "Unknown")
    rating = place_dict.get("rating", 0)
    review_count = place_dict.get("review_count", 0)
    address = place_dict.get("address", "")
    categories = ", ".join(place_dict.get("categories", [])[:3])
    lines = [f"{prefix}{name}", f"    Rating: {rating}/5 ({review_count:,} reviews)"]
    if categories:
        lines.append(f"    Type: {categories}")
    if address:
        lines.append(f"    Address: {address}")
    if place_dict.get("website"):
        lines.append(f"    Web: {place_dict['website']}")
    if place_dict.get("phone"):
        lines.append(f"    Phone: {place_dict['phone']}")
    if place_dict.get("email"):
        lines.append(f"    Email: {place_dict['email']}")
    return "\n".join(lines)
