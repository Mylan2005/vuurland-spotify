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
    # Public Spotify track confirms the official title is One Day Like This,
    # never "On a Day Like This". No similar title is generalized.
    if (a.casefold(), t.casefold()) == ("elbow", "on a day like this"):
        return a, "One Day Like This"
    # Verified RadioBox shortening: full Spotify title is Pearly-Dewdrops' Drops.
    # Keep normal artist, title, edition and market checks.
    if (a.casefold(), t.casefold()) == ("cocteau twins", "pearly-dewdrops"):
        return a, "Pearly-Dewdrops' Drops"
    # A full spelled-out catalog number is proven for this exact AIR song.
    # Not a general "No.1" title replacement for arbitrary songs.
    if (a.casefold(), t.casefold()) == ("air", "radio no.1"):
        return a, "Radio Number 1"
    # Preserve the exact edit: this is not the original or extended remix.
    if (a.casefold(), t.casefold()) == (
        "chicane vs. natasha bedingfield", "bruised water (michael woods edit)"
    ):
        return "Chicane feat. Natasha Bedingfield", "Bruised Water - Michael Woods Edit"
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
