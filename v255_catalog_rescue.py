"""v255: documented Spotify catalog variants; no match or URI is auto-approved.

Only reuses an existing later search slot to target known source albums.
The existing normal matcher still checks artist, exact song, edition, market.
"""


def catalog_metadata(artist, title):
    a, t = str(artist or "").strip(), str(title or "").strip()
    if (a.casefold(), t.casefold()) == (
        "martin kohlstedt", "ell (christian löffler rework)"
    ):
        return a, "ELL - Christian Loeffler Rework"
    return a, t


# Spotify's album pages confirm these exact studio recordings.
_ALBUMS = {
    ("curve", "chinese burn"): "Come Clean",
    ("palace brothers", "you will miss me when i burn"): "Days in the Wake",
    ("beady eye", "for anyone"): "Different Gear, Still Speeding",
}


def safe_catalog_album_query(artist, title, variant):
    if int(variant or 0) < 1:
        return None
    key = (str(artist or "").strip().casefold(),
           str(title or "").strip().casefold())
    album = _ALBUMS.get(key)
    if not album:
        return None
    # Artist and song must still pass local full matcher. Single search call.
    a, t = (str(value or "").replace('"', ' ').strip() for value in (artist, title))
    return f'"{a}" "{t}" "{album}"'


def catalog_verified_retry(artist, title):
    a, t = str(artist or "").strip(), str(title or "").strip()
    return (a.casefold(), t.casefold()) in _ALBUMS or catalog_metadata(a, t) != (a, t)
