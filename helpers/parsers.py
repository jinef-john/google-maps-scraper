import json
import re

from models import Place, Review, Reviewer, OpeningHours


def _strip_xssi(text):
    """Remove the XSSI/anti-hijacking prefix from Google responses."""
    if text.startswith(")]}'"):
        text = text[4:].lstrip("\n")
    return text


def _safe_get(arr, *indices, default=None):
    """Safely traverse nested arrays by index path."""
    current = arr
    for idx in indices:
        if not isinstance(current, (list, tuple)):
            return default
        if idx < 0 or idx >= len(current):
            return default
        current = current[idx]
    return current if current is not None else default


def parse_search_response(text):
    """Parse the search results (tbm=map) response.

    Returns a list of dicts: {place_id, name, lat, lng, rating, review_count, address, categories}
    """
    # Handle the outer wrapper: {"c":0,"d":"..."}
    try:
        decoder = json.JSONDecoder()
        outer, _ = decoder.raw_decode(text)
        if isinstance(outer, dict) and "d" in outer:
            inner_text = outer["d"]
        else:
            inner_text = text
    except (json.JSONDecodeError, ValueError):
        inner_text = text

    inner_text = _strip_xssi(inner_text)

    try:
        data = json.loads(inner_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Find the listings array: it's a list of [None, place_data] pairs
    # Usually at a high index in the root array (e.g. data[64])
    listings = []
    for i in range(len(data) - 1, -1, -1):
        elem = data[i]
        if not isinstance(elem, list) or len(elem) < 2:
            continue
        # Check if this looks like a listings array: list of [None, [...260+...]] pairs
        first_entry = elem[0]
        if isinstance(first_entry, list) and len(first_entry) >= 2:
            inner_data = first_entry[1]
            if isinstance(inner_data, list) and len(inner_data) > 50:
                listings = elem
                break

    results = []
    for item in listings:
        if not isinstance(item, list) or len(item) < 2:
            continue

        pd = item[1]
        if not isinstance(pd, list) or len(pd) < 20:
            continue

        place_id = _safe_get(pd, 10, default="")
        if not isinstance(place_id, str) or "0x" not in place_id:
            continue

        name = _safe_get(pd, 11, default="") or ""
        lat = _safe_get(pd, 9, 2, default=0.0)
        lng = _safe_get(pd, 9, 3, default=0.0)

        # Rating block at pd[4]
        rating_block = _safe_get(pd, 4, default=[])
        rating = _safe_get(rating_block, 7, default=0.0) if isinstance(rating_block, list) else 0.0
        review_count = _safe_get(rating_block, 8, default=0) if isinstance(rating_block, list) else 0

        # Categories at pd[13]
        categories = _safe_get(pd, 13, default=[])
        if isinstance(categories, str):
            categories = [categories]
        elif not isinstance(categories, list):
            categories = []

        # Address at pd[18]
        address = _safe_get(pd, 18, default="") or ""

        results.append({
            "place_id": place_id,
            "name": name,
            "lat": lat if isinstance(lat, (int, float)) else 0.0,
            "lng": lng if isinstance(lng, (int, float)) else 0.0,
            "rating": rating if isinstance(rating, (int, float)) else 0.0,
            "review_count": review_count if isinstance(review_count, int) else 0,
            "categories": categories,
            "address": address,
        })

    # Fallback: knowledge panel format (data[0][1] = direct entity results)
    # Each entity has a 260-elem place block at entity[14]
    if not results:
        entities = _safe_get(data, 0, 1, default=[])
        if isinstance(entities, list):
            for entity in entities:
                pd = _safe_get(entity, 14, default=None)
                if not isinstance(pd, list) or len(pd) < 20:
                    continue
                place_id = _safe_get(pd, 10, default="")
                if not isinstance(place_id, str) or "0x" not in place_id:
                    continue
                name = _safe_get(pd, 11, default="") or ""
                lat = _safe_get(pd, 9, 2, default=0.0)
                lng = _safe_get(pd, 9, 3, default=0.0)
                rating_block = _safe_get(pd, 4, default=[])
                rating = _safe_get(rating_block, 7, default=0.0) if isinstance(rating_block, list) else 0.0
                review_count = _safe_get(rating_block, 8, default=0) if isinstance(rating_block, list) else 0
                categories = _safe_get(pd, 13, default=[])
                if not isinstance(categories, list):
                    categories = []
                address = _safe_get(pd, 18, default="") or ""
                results.append({
                    "place_id": place_id,
                    "name": name,
                    "lat": lat if isinstance(lat, (int, float)) else 0.0,
                    "lng": lng if isinstance(lng, (int, float)) else 0.0,
                    "rating": rating if isinstance(rating, (int, float)) else 0.0,
                    "review_count": review_count if isinstance(review_count, int) else 0,
                    "categories": categories,
                    "address": address,
                })

    return results


def parse_place_response(text):
    """Parse the place details (/maps/preview/place) response.

    Returns a Place object with all available data.
    """
    text = _strip_xssi(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    place = Place()

    info = _safe_get(data, 1, default=None)
    if not isinstance(info, list) or len(info) < 50:
        info = _safe_get(data, 6, default=[])

    # Place ID - usually at position that contains "0x..."
    place_id = _find_place_id(data)
    place.place_id = place_id or ""

    # Address components (array of address lines)
    addr_parts = _safe_get(info, 2, default=[])
    if isinstance(addr_parts, list) and all(isinstance(a, str) for a in addr_parts):
        place.address_components = addr_parts
        place.address = ", ".join(addr_parts)

    # Rating and review count
    rating_block = _safe_get(info, 4, default=[])
    if isinstance(rating_block, list):
        place.rating = _safe_get(rating_block, 7, default=0.0)
        place.review_count = _safe_get(rating_block, 8, default=0)
        if not place.rating:
            place.rating = _safe_get(rating_block, 0, 7, default=0.0)
        if not place.review_count:
            place.review_count = _safe_get(rating_block, 0, 8, default=0)
        if not place.review_count:
            review_link = _safe_get(rating_block, 3, default=None)
            if isinstance(review_link, list):
                review_text = _safe_get(review_link, 1, default="")
                if isinstance(review_text, str) and "review" in review_text.lower():
                    nums = re.findall(r"\d+", review_text.replace(",", ""))
                    if nums:
                        place.review_count = int(nums[0])

    # Website
    website_block = _safe_get(info, 7, default=None)
    if isinstance(website_block, list) and len(website_block) > 0:
        place.website = _safe_get(website_block, 0, default="")
    elif isinstance(website_block, str):
        place.website = website_block

    # Coordinates
    coord_block = _safe_get(info, 9, default=[])
    if isinstance(coord_block, list) and len(coord_block) >= 4:
        place.lat = _safe_get(coord_block, 2, default=0.0)
        place.lng = _safe_get(coord_block, 3, default=0.0)

    # Name
    name = _safe_get(info, 11, default="")
    if isinstance(name, str) and name:
        place.name = name

    # Categories
    categories = _safe_get(info, 13, default=[])
    if isinstance(categories, list):
        place.categories = [c for c in categories if isinstance(c, str)]

    # Phone — directly at info[178][0][0], fallback to recursive search
    phone_block = _safe_get(info, 178, default=None)
    if isinstance(phone_block, list) and phone_block:
        place.phone = _safe_get(phone_block, 0, 0, default="") or ""
    if not place.phone:
        place.phone = _find_phone(info) or ""

    # Opening hours — info[203][0][0] → list of [day, idx, date, [[hours_text, times]], ...]
    hours_block = _safe_get(info, 203, default=None)
    if isinstance(hours_block, list):
        days_list = _safe_get(hours_block, 0, default=[])
        if isinstance(days_list, list):
            oh = OpeningHours()
            for day_entry in days_list:
                if not isinstance(day_entry, list) or len(day_entry) < 4:
                    continue
                day_name = _safe_get(day_entry, 0, default="")
                hours_slots = _safe_get(day_entry, 3, default=[])
                if isinstance(hours_slots, list) and hours_slots:
                    hours_text = _safe_get(hours_slots, 0, 0, default="")
                    if isinstance(day_name, str) and isinstance(hours_text, str) and day_name:
                        oh.periods.append({"day": day_name, "hours": hours_text})
                        oh.weekday_text.append(f"{day_name}: {hours_text}")
            if oh.periods:
                place.opening_hours = oh

    # Photos
    place.photos = _extract_photo_urls(data)

    # Price level: info[4][2] = "$$" style, info[4][10] = "£100 or above" style
    price_level = _safe_get(info, 4, 2, default=None)
    if not isinstance(price_level, str) or not price_level:
        price_level = _safe_get(info, 4, 10, default=None)
    if isinstance(price_level, str) and price_level:
        place.price_level = price_level

    # Description / editorial summary
    description = _safe_get(info, 154, 0, 0, default=None)
    if isinstance(description, str) and description:
        place.description = description

    # About (services, accessibility, dining options, etc.)
    place.about = _parse_about(info)

    # Menu (restaurants only)
    place.menu = _parse_menu(info)

    # Booking / reservation links
    booking_raw = _safe_get(info, 46, default=None)
    if isinstance(booking_raw, list):
        for entry in booking_raw:
            url = _safe_get(entry, 0, default=None)
            domain = _safe_get(entry, 1, default=None)
            if isinstance(url, str) and url.startswith("http"):
                place.booking_links.append({"url": url, "domain": domain or ""})

    # Featured review snippets
    place.featured_review_snippets = _extract_review_snippets(info)

    # Store raw data for advanced users
    place.raw_data = data

    return place


def parse_reviews_response(text):
    """Parse the reviews listing (/maps/rpc/listugcposts) response.

    Returns:
        tuple: (list of Review objects, next_cursor string or None)
    """
    text = _strip_xssi(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], None

    # data[1] = next page cursor (or None if last page)
    next_cursor = _safe_get(data, 1, default=None)

    # data[2] = list of review entries
    review_entries = _safe_get(data, 2, default=[])
    if not isinstance(review_entries, list):
        return [], next_cursor

    reviews = []
    for entry in review_entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue

        review = _parse_single_review(entry)
        if review:
            reviews.append(review)

    return reviews, next_cursor


def _parse_single_review(entry):
    """Parse a single review entry.

    Structure:
        entry[0] = inner_list
        inner_list[0] = review_id (string)
        inner_list[1] = metadata: [place_id, None, ts, ts, author_block, None, date_text, ...]
        inner_list[2] = content: [[rating], None*13, [lang], [[text, ...]]]
        inner_list[3] = reply: [None, ts, ts, date_text, ..., [lang], [[reply_text, ...]]]
    """
    review = Review()

    # entry[0] is the inner review list
    inner = _safe_get(entry, 0, default=[])
    if not isinstance(inner, list) or len(inner) < 3:
        return None

    # Review ID
    review.review_id = _safe_get(inner, 0, default="")
    if not isinstance(review.review_id, str):
        return None

    # Metadata block (inner[1])
    meta = _safe_get(inner, 1, default=[])
    if isinstance(meta, list):
        # Author info: meta[4][5] = [name, avatar, [profile_urls], user_id, None, guide_level, ...]
        author_block = _safe_get(meta, 4, default=[])
        author_info = _safe_get(author_block, 5, default=[])
        if isinstance(author_info, list) and len(author_info) > 3:
            reviewer = Reviewer()
            reviewer.name = _safe_get(author_info, 0, default="") or ""
            reviewer.avatar_url = _safe_get(author_info, 1, default="") or ""
            profile_urls = _safe_get(author_info, 2, default=[])
            if isinstance(profile_urls, list) and profile_urls:
                reviewer.profile_url = profile_urls[0] if isinstance(profile_urls[0], str) else ""
            reviewer.user_id = _safe_get(author_info, 3, default="") or ""

            # Guide level at author_info[5] (>0 means local guide)
            guide_level = _safe_get(author_info, 5, default=0)
            reviewer.is_local_guide = isinstance(guide_level, int) and guide_level > 0

            # Review count display text at author_info[10][0]
            review_meta = _safe_get(author_info, 10, default=[])
            if isinstance(review_meta, list) and review_meta:
                reviewer.review_count = _safe_get(review_meta, 0, default="") or ""

            review.reviewer = reviewer

        # Date text: meta[6]
        review.date = _safe_get(meta, 6, default="") or ""

    # Content block (inner[2])
    content = _safe_get(inner, 2, default=[])
    if isinstance(content, list):
        # Rating: content[0] = [rating_int]
        rating_arr = _safe_get(content, 0, default=[])
        if isinstance(rating_arr, list) and rating_arr:
            review.rating = int(_safe_get(rating_arr, 0, default=0) or 0)

        # Language: content[14] = ["en"]
        lang_arr = _safe_get(content, 14, default=[])
        if isinstance(lang_arr, list) and lang_arr:
            review.language = lang_arr[0] if isinstance(lang_arr[0], str) else ""

        # Review text: content[15] = [["full review text", None, [start, end]]]
        text_blocks = _safe_get(content, 15, default=[])
        if isinstance(text_blocks, list):
            for tb in text_blocks:
                if isinstance(tb, list) and tb and isinstance(tb[0], str):
                    review.text = tb[0]
                    break

        # Photos: content[2] = list of photo objects; URL at photo[1][6][0]
        photo_entries = _safe_get(content, 2, default=[])
        if isinstance(photo_entries, list):
            for photo in photo_entries:
                url = _safe_get(photo, 1, 6, 0, default=None)
                if isinstance(url, str) and url.startswith("http"):
                    review.photos.append(url)
    reply = _safe_get(inner, 3, default=None)
    if isinstance(reply, list) and len(reply) > 3:
        # Reply date: reply[3]
        review.owner_reply_date = _safe_get(reply, 3, default="") or ""

        # Reply text: reply[14] = [["reply text", None, [start, end]]]
        reply_text_blocks = _safe_get(reply, 14, default=[])
        if isinstance(reply_text_blocks, list):
            for tb in reply_text_blocks:
                if isinstance(tb, list) and tb and isinstance(tb[0], str):
                    review.owner_reply = tb[0]
                    break

    return review


def _find_place_id(data):
    """Recursively search for a place ID string (0x...format)."""
    pattern = re.compile(r"0x[0-9a-f]+:0x[0-9a-f]+")

    def _search(obj, depth=0):
        if depth > 5:
            return None
        if isinstance(obj, str):
            match = pattern.search(obj)
            if match:
                return match.group(0)
        elif isinstance(obj, list):
            for item in obj[:20]:  # limit search breadth
                result = _search(item, depth + 1)
                if result:
                    return result
        return None

    return _search(data)


def _find_phone(data):
    """Search for phone number pattern in the data."""
    phone_pattern = re.compile(r"\+?\d[\d\s\-()]{7,}")

    def _search(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, str) and phone_pattern.match(obj) and len(obj) < 25:
            return obj
        elif isinstance(obj, list):
            for item in obj[:30]:
                result = _search(item, depth + 1)
                if result:
                    return result
        return None

    return _search(data)


def _extract_photo_urls(data):
    """Extract photo URLs from the response data."""
    photos = []
    photo_pattern = re.compile(r"https://lh[35]\.googleusercontent\.com/[^\s\"]+")

    def _search(obj, depth=0):
        if depth > 8:
            return
        if isinstance(obj, str):
            if "googleusercontent.com" in obj and obj.startswith("http"):
                photos.append(obj)
        elif isinstance(obj, list):
            for item in obj[:50]:
                _search(item, depth + 1)
                if len(photos) >= 20:
                    return

    _search(data)
    return list(dict.fromkeys(photos))[:20]  # deduplicate, max 20


def _extract_review_snippets(info):
    """Extract featured review snippets from place info."""
    snippets = []
    if not isinstance(info, list):
        return snippets

    def _search(obj, depth=0):
        if depth > 6 or len(snippets) >= 5:
            return
        if isinstance(obj, str) and obj.startswith('"') and obj.endswith('"'):
            snippets.append(obj.strip('"'))
        elif isinstance(obj, list):
            for item in obj[:30]:
                _search(item, depth + 1)

    _search(info)
    return snippets


def _parse_about(info):
    """Parse the about/services/accessibility section from info[100].

    Returns a list of {group, attributes: [{label, present}]} dicts.
    """
    # info[100] = [null, [group1, group2, ...]]
    # Each group: [group_uri_or_null, group_label, [attr1, attr2, ...], ...]
    # Each attr:  [attr_uri, label, [1, [[present_int, text]], [present_int, ...]], ...]
    groups_raw = _safe_get(info, 100, 1, default=None)
    if not isinstance(groups_raw, list):
        return []

    result = []
    for group in groups_raw:
        if not isinstance(group, list) or len(group) < 2:
            continue
        group_name = _safe_get(group, 0, default="") or ""
        attrs_raw = _safe_get(group, 2, default=None)
        if not isinstance(attrs_raw, list):
            attrs_raw = _safe_get(group, 1, default=[]) or []
        attrs = []
        for attr in attrs_raw:
            if not isinstance(attr, list):
                continue
            label = _safe_get(attr, 1, default=None)
            if not isinstance(label, str) or not label:
                continue
            present = _safe_get(attr, 2, 2, 0, default=None)
            attrs.append({"label": label, "present": present == 1})
        if attrs:
            result.append({"group": group_name, "attributes": attrs})

    return result


def _parse_menu(info):
    """Parse embedded menu data from info[125] (restaurants only).

    Returns a list of {category, items: [{name, description, price, photo}]} dicts.
    """
    # info[125][0] = list of menu books; each book[1] = list of categories
    books = _safe_get(info, 125, 0, default=None)
    if not isinstance(books, list):
        return []

    result = []
    for book in books:
        categories_raw = _safe_get(book, 1, default=None)
        if not isinstance(categories_raw, list):
            continue
        for cat in categories_raw:
            cat_name = _safe_get(cat, 0, 0, default="") or ""
            items_raw = _safe_get(cat, 1, default=None)
            if not isinstance(items_raw, list):
                continue
            items = []
            for item in items_raw:
                name = _safe_get(item, 0, 0, 0, default="") or ""
                if not name:
                    continue
                desc = _safe_get(item, 0, 0, 1, default="") or ""
                price = _safe_get(item, 1, 0, default="") or ""
                photo_url = _safe_get(item, 5, 0, 0, default="") or ""
                items.append({"name": name, "description": desc, "price": price, "photo": photo_url})
            if items:
                result.append({"category": cat_name, "items": items})

    return result
