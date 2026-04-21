from urllib.parse import quote


BASE = "https://www.google.com"


def search_url(query, lat, lng, zoom=13, lang="en", gl="us", page_size=20, start=0):
    """Build the /search?tbm=map URL for listing places.

    Args:
        query: Search string (e.g. "hospitals in Nairobi")
        lat: Center latitude
        lng: Center longitude
        zoom: Map zoom level (affects search radius)
        lang: Language code
        gl: Country code
        page_size: Results per page (default 20)
        start: Offset for pagination (0, 20, 40, ...)
    """
    # Calculate the map span based on zoom
    # At zoom 13, span is roughly 0.1 degrees
    span = 360 / (2 ** zoom)
    d_value = span * 111320  # approx meters

    pb = (
        f"!4m12!1m3!1d{d_value}!2d{lng}!3d{lat}"
        f"!2m3!1f0!2f0!3f0!3m2!1i1280!2i593!4f13.1"
        f"!7i{page_size}"
    )
    if start > 0:
        pb += f"!8i{start}"

    pb += (
        "!10b1"
        "!12m25!1m5!18b1!30b1!31m1!1b1!34e1!2m4!5m1!6e2!20e3!39b1"
        "!10b1!12b1!13b1!16b1!17m1!3e1!20m3!5e2!6b1!14b1!46m1!1b0!96b1!99b1"
        "!19m4!2m3!1i360!2i120!4i8"
        "!20m65!2m2!1i203!2i100!3m2!2i4!5b1"
        "!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
        "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3"
        "!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2"
        "!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
        "!15m16!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
        "!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
        "!22m2!1sdummy!7e81"
        "!24m109!1m27!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
        "!18m16!3b1!4b1!5b1!6b1!9b1!13b1!14b1!17b1!20b1!21b1!22b1"
        "!32b1!33m1!1b1!34b1!36e2"
        "!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6"
        "!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1"
        "!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1"
        "!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298"
        "!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1"
        "!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4"
        "!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts"
        "!6m1!1e1!9b1!89b1!90m2!1m1!1e2"
        "!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1"
        "!117b1!122m1!1b1!126b1!127b1!128m1!1b0"
        "!26m4!2m3!1i80!2i92!4i8"
        "!30m28!1m6!1m2!1i0!2i0!2m2!1i530!2i593"
        "!1m6!1m2!1i1230!2i0!2m2!1i1280!2i593"
        "!1m6!1m2!1i0!2i0!2m2!1i1280!2i20"
        "!1m6!1m2!1i0!2i573!2m2!1i1280!2i593"
        "!34m19!2b1!3b1!4b1!6b1!8m6!1b1!3b1!4b1!5b1!6b1!7b1"
        "!9b1!12b1!14b1!20b1!23b1!25b1!26b1!31b1"
        "!37m1!1e81!42b1!47m0"
        "!49m10!3b1!6m2!1b1!2b1!7m2!1e3!2b1!8b1!9b1!10e2"
        "!50m4!2e2!3m2!1b1!3b1"
        "!67m5!7b1!10b1!14b1!15m1!1b0!69i775!77b1"
    )

    encoded_query = quote(query)
    return (
        f"{BASE}/search?tbm=map&authuser=0&hl={lang}&gl={gl}"
        f"&pb={pb}&q={encoded_query}&tch=1&ech=1&psi=dummy.{int(__import__('time').time()*1000)}.1"
    )


def place_url(place_id, lat, lng, query="", lang="en", gl="us"):
    """Build the /maps/preview/place URL for full place details."""
    encoded_place_id = quote(place_id, safe="")
    encoded_query = quote(query, safe="") if query else ""

    pb = (
        f"!1m6"
        f"!1s{encoded_place_id}"
        f"!3m1!1d1000"
        f"!4m2!3d{lat}!4d{lng}"
        "!3m1!1e3"
        "!15m111!1m29!4e2!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
        "!18m17!3b1!4b1!5b1!6b1!9b1!13b1!14b1!17b1!20b1!21b1!22b1!30b1!32b1!33m1!1b1!34b1!36e2"
        "!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1"
        "!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1"
        "!65m5!3m4!1m3!1m2!1i224!2i298"
        "!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1"
        "!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4"
        "!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts"
        "!6m1!1e1!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1"
        "!103b1!113b1!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1!128m1!1b0"
    )

    url = f"{BASE}/maps/preview/place?authuser=0&hl={lang}&gl={gl}&pb={pb}"
    if encoded_query:
        url += f"&q={encoded_query}"
    return url


def reviews_url(place_id, page_size=10, cursor="", lang="en", gl="us"):
    """Build the /maps/rpc/listugcposts URL for paginated reviews.

    Args:
        place_id: The hex place ID
        page_size: Reviews per page (default 10)
        cursor: Pagination cursor (empty string for first page)
        lang: Language code
        gl: Country code
    """
    encoded_place_id = quote(place_id, safe="")
    encoded_cursor = quote(cursor, safe="") if cursor else ""

    pb = (
        f"!1m6!1s{encoded_place_id}"
        "!6m4!4m1!1e1!4m1!1e3"
        f"!2m2!1i{page_size}!2s{encoded_cursor}"
        "!5m2!1sdummy!7e81"
        "!8m9!2b1!3b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1"
        "!11m4!1e3!2e1!6m1!1i2"
        "!13m1!1e1"
    )

    return f"{BASE}/maps/rpc/listugcposts?authuser=0&hl={lang}&gl={gl}&pb={pb}"
