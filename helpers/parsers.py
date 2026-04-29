"""Response parsers for Google Maps search, place details, and reviews."""

import json
import re

from models import OpeningHours, Place, Review, Reviewer


def _strip_xssi(text):
    if text.startswith(")]}'"):
        text = text[4:].lstrip("\n")
    return text


def _get(data, *indices, default=None):
    current = data
    for idx in indices:
        if not isinstance(current, (list, tuple)):
            return default
        if idx < 0 or idx >= len(current):
            return default
        current = current[idx]
    return current if current is not None else default


def _find_place_id(data):
    pat = re.compile(r"0x[0-9a-f]+:0x[0-9a-f]+")

    def _search(obj, depth=0):
        if depth > 5:
            return None
        if isinstance(obj, str):
            m = pat.search(obj)
            return m.group(0) if m else None
        if isinstance(obj, list):
            for item in obj[:20]:
                r = _search(item, depth + 1)
                if r:
                    return r
        return None

    return _search(data)


def _find_phone(data):
    pat = re.compile(r"\+?\d[\d\s\-()]{7,}")

    def _search(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, str) and pat.match(obj) and len(obj) < 25:
            return obj
        if isinstance(obj, list):
            for item in obj[:30]:
                r = _search(item, depth + 1)
                if r:
                    return r
        return None

    return _search(data)


def _extract_photos(data, limit=20):
    photos = []

    def _search(obj, depth=0):
        if depth > 8 or len(photos) >= limit:
            return
        if isinstance(obj, str) and "googleusercontent.com" in obj and obj.startswith("http"):
            photos.append(obj)
        elif isinstance(obj, list):
            for item in obj[:50]:
                _search(item, depth + 1)

    _search(data)
    return list(dict.fromkeys(photos))[:limit]


def _parse_about(info):
    groups_raw = _get(info, 100, 1)
    if not isinstance(groups_raw, list):
        return []

    result = []
    for group in groups_raw:
        if not isinstance(group, list) or len(group) < 2:
            continue
        gname = _get(group, 0, default="") or ""
        attrs_raw = _get(group, 2)
        if not isinstance(attrs_raw, list):
            attrs_raw = _get(group, 1) or []
        attrs = []
        for attr in attrs_raw if isinstance(attrs_raw, list) else []:
            if not isinstance(attr, list):
                continue
            label = _get(attr, 1)
            if not isinstance(label, str) or not label:
                continue
            present = _get(attr, 2, 2, 0)
            attrs.append({"label": label, "present": present == 1})
        if attrs:
            result.append({"group": gname, "attributes": attrs})
    return result


def _parse_menu(info):
    sections = _get(info, 125, 0, 0, 1)
    if not isinstance(sections, list):
        return []

    result = []
    for section in sections:
        if not isinstance(section, list) or len(section) < 2:
            continue
        category = _get(section, 0, 0, default="") or ""
        items_raw = _get(section, 1, 0)
        if not isinstance(items_raw, list):
            continue
        items = []
        for item in items_raw:
            if not isinstance(item, list):
                continue
            name = _get(item, 0, 0, default="") or ""
            if not name:
                continue
            items.append({
                "name": name,
                "description": _get(item, 0, 1, default="") or "",
                "price": _get(item, 1, 0, default="") or "",
                "photo": _get(item, 5, 0, 0, default="") or "",
            })
        if items:
            result.append({"category": category, "items": items})
    return result


def parse_search_response(text):
    """Parse search results into place stubs."""
    try:
        decoder = json.JSONDecoder()
        outer, _ = decoder.raw_decode(text)
        inner_text = outer["d"] if isinstance(outer, dict) and "d" in outer else text
    except Exception:
        inner_text = text

    inner_text = _strip_xssi(inner_text)
    try:
        data = json.loads(inner_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Find the listings array
    listings = []
    for i in range(len(data) - 1, -1, -1):
        elem = data[i]
        if not isinstance(elem, list):
            continue
        for entry in elem:
            if isinstance(entry, list) and len(entry) >= 2:
                if isinstance(entry[1], list) and len(entry[1]) > 50:
                    listings = elem
                    break
        if listings:
            break

    def _extract(pd):
        pid = _get(pd, 10, default="")
        if not isinstance(pid, str) or "0x" not in pid:
            return None
        rb = _get(pd, 4, default=[])
        cats = _get(pd, 13, default=[])
        if isinstance(cats, str):
            cats = [cats]
        elif not isinstance(cats, list):
            cats = []
        return {
            "place_id": pid,
            "name": _get(pd, 11, default="") or "",
            "lat": _get(pd, 9, 2, default=0.0),
            "lng": _get(pd, 9, 3, default=0.0),
            "rating": _get(rb, 7, default=0.0) if isinstance(rb, list) else 0.0,
            "review_count": _get(rb, 8, default=0) if isinstance(rb, list) else 0,
            "categories": cats,
            "address": _get(pd, 18, default="") or "",
        }

    results = []
    for item in listings:
        if isinstance(item, list) and len(item) >= 2:
            r = _extract(item[1])
            if r:
                results.append(r)

    # Fallback: knowledge panel format
    if not results:
        entities = _get(data, 0, 1, default=[])
        if isinstance(entities, list):
            for entity in entities:
                pd = _get(entity, 14)
                if isinstance(pd, list) and len(pd) > 20:
                    r = _extract(pd)
                    if r:
                        results.append(r)

    # Coerce types
    for r in results:
        r["lat"] = float(r["lat"]) if isinstance(r["lat"], (int, float)) else 0.0
        r["lng"] = float(r["lng"]) if isinstance(r["lng"], (int, float)) else 0.0
        r["rating"] = float(r["rating"]) if isinstance(r["rating"], (int, float)) else 0.0
        r["review_count"] = int(r["review_count"]) if isinstance(r["review_count"], (int, float)) else 0
    return results


def parse_place_response(text):
    """Parse place detail response into a Place dataclass."""
    text = _strip_xssi(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    place = Place()
    place.place_id = _find_place_id(data) or ""

    info = _get(data, 1)
    if not isinstance(info, list) or len(info) < 50:
        info = _get(data, 6, default=[])

    # Address
    addr_parts = _get(info, 2, default=[])
    if isinstance(addr_parts, list) and all(isinstance(a, str) for a in addr_parts):
        place.address_components = addr_parts
        place.address = ", ".join(addr_parts)

    # Rating + review count
    rb = _get(info, 4, default=[])
    if isinstance(rb, list):
        place.rating = _get(rb, 7, default=0.0) or _get(rb, 0, 7, default=0.0)
        place.review_count = _get(rb, 8, default=0) or _get(rb, 0, 8, default=0)
        if not place.review_count:
            rl = _get(rb, 3)
            if isinstance(rl, list):
                rt = _get(rl, 1, default="")
                if isinstance(rt, str) and "review" in rt.lower():
                    nums = re.findall(r"\d+", rt.replace(",", ""))
                    if nums:
                        place.review_count = int(nums[0])

    # Website
    wb = _get(info, 7)
    if isinstance(wb, list) and wb:
        place.website = _get(wb, 0, default="")
    elif isinstance(wb, str):
        place.website = wb

    # Coordinates
    cb = _get(info, 9, default=[])
    if isinstance(cb, list) and len(cb) >= 4:
        place.lat = float(_get(cb, 2, default=0.0) or 0)
        place.lng = float(_get(cb, 3, default=0.0) or 0)

    # Name
    name = _get(info, 11, default="")
    if isinstance(name, str) and name:
        place.name = name

    # Categories
    cats = _get(info, 13, default=[])
    if isinstance(cats, list):
        place.categories = [c for c in cats if isinstance(c, str)]

    # Phone
    pb = _get(info, 178)
    if isinstance(pb, list) and pb:
        place.phone = _get(pb, 0, 0, default="") or ""
    if not place.phone:
        place.phone = _find_phone(info) or ""

    # Opening hours
    hb = _get(info, 203)
    if isinstance(hb, list):
        days = _get(hb, 0, default=[])
        if isinstance(days, list):
            oh = OpeningHours()
            for de in days:
                if not isinstance(de, list) or len(de) < 4:
                    continue
                dn = _get(de, 0, default="")
                hs = _get(de, 3, default=[])
                if isinstance(hs, list) and hs:
                    ht = _get(hs, 0, 0, default="")
                    if isinstance(dn, str) and isinstance(ht, str) and dn:
                        oh.periods.append({"day": dn, "hours": ht})
                        oh.weekday_text.append(f"{dn}: {ht}")
            if oh.periods:
                place.opening_hours = oh

    # Photos
    place.photos = _extract_photos(data)

    # Price level
    pl = _get(info, 4, 2)
    if not isinstance(pl, str) or not pl:
        pl = _get(info, 4, 10)
    if isinstance(pl, str) and pl:
        place.price_level = pl

    # Description
    desc = _get(info, 154, 0, 0)
    if not isinstance(desc, str) or not desc:
        desc = _get(info, 32, 1, 1) or _get(info, 32, 0, 1)
    if isinstance(desc, str) and desc:
        place.description = desc

    # About + hotel badges
    place.about = _parse_about(info)
    badges = _get(info, 64, 2)
    if isinstance(badges, list):
        attrs = []
        for badge in badges:
            label = _get(badge, 2)
            has = _get(badge, 3, default=0)
            if isinstance(label, str) and label:
                attrs.append({"label": label, "present": has == 1})
        if attrs:
            place.about.append({"group": "amenities", "attributes": attrs})

    # Menu
    place.menu = _parse_menu(info)

    # Booking links
    booking = _get(info, 46)
    if isinstance(booking, list):
        for entry in booking:
            url = _get(entry, 0)
            domain = _get(entry, 1)
            if isinstance(url, str) and url.startswith("http"):
                place.booking_links.append({"url": url, "domain": domain or ""})

    return place


def parse_reviews_response(text):
    """Parse reviews response. Returns (reviews, next_cursor)."""
    text = _strip_xssi(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], None

    next_cursor = _get(data, 1)
    entries = _get(data, 2, default=[])
    if not isinstance(entries, list):
        return [], next_cursor

    reviews = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        review = _parse_single_review(entry)
        if review:
            reviews.append(review)
    return reviews, next_cursor if isinstance(next_cursor, str) else None


def _parse_single_review(entry):
    """Parse a single review entry."""
    review = Review()
    inner = _get(entry, 0, default=[])
    if not isinstance(inner, list) or len(inner) < 3:
        return None

    review.review_id = _get(inner, 0, default="")
    if not isinstance(review.review_id, str):
        return None

    meta = _get(inner, 1, default=[])
    if isinstance(meta, list):
        # Author info path: meta[4][5] = [name, avatar, [profile_urls], user_id, None, guide_level, ...]
        author_block = _get(meta, 4, default=[])
        author_info = _get(author_block, 5, default=[])
        if isinstance(author_info, list) and len(author_info) > 3:
            r = Reviewer()
            r.name = _get(author_info, 0, default="") or ""
            r.avatar_url = _get(author_info, 1, default="") or ""
            profile_urls = _get(author_info, 2, default=[])
            if isinstance(profile_urls, list) and profile_urls:
                r.profile_url = profile_urls[0] if isinstance(profile_urls[0], str) else ""
            r.user_id = _get(author_info, 3, default="") or ""
            guide_level = _get(author_info, 5, default=0)
            r.is_local_guide = isinstance(guide_level, int) and guide_level > 0
            review_meta = _get(author_info, 10, default=[])
            if isinstance(review_meta, list) and review_meta:
                r.review_count = _get(review_meta, 0, default="") or ""
            review.reviewer = r

        review.date = _get(meta, 6, default="") or ""

    content = _get(inner, 2, default=[])
    if isinstance(content, list):
        rating_arr = _get(content, 0, default=[])
        if isinstance(rating_arr, list) and rating_arr:
            review.rating = int(_get(rating_arr, 0, default=0) or 0)

        lang_arr = _get(content, 14, default=[])
        if isinstance(lang_arr, list) and lang_arr:
            review.language = lang_arr[0] if isinstance(lang_arr[0], str) else ""

        text_blocks = _get(content, 15, default=[])
        if isinstance(text_blocks, list):
            for tb in text_blocks:
                if isinstance(tb, list) and tb and isinstance(tb[0], str):
                    review.text = tb[0]
                    break

        photo_entries = _get(content, 2, default=[])
        if isinstance(photo_entries, list):
            for photo in photo_entries:
                url = _get(photo, 1, 6, 0)
                if isinstance(url, str) and url.startswith("http"):
                    review.photos.append(url)

    reply = _get(inner, 3)
    if isinstance(reply, list) and len(reply) > 3:
        review.owner_reply_date = _get(reply, 3, default="") or ""
        reply_text_blocks = _get(reply, 14, default=[])
        if isinstance(reply_text_blocks, list):
            for tb in reply_text_blocks:
                if isinstance(tb, list) and tb and isinstance(tb[0], str):
                    review.owner_reply = tb[0]
                    break

    return review
