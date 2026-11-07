"""v208: trailing explicit feature belongs to ARTIST metadata.

A complete (feat. ARTIST) / (featuring ARTIST) suffix gets reformatted to
an explicit collaboration credit, NOT dropped. All other metadata untouched.
"""
import re

_EXPLICIT_FEATURE = re.compile(
    r"^(.+?)\s+\(\s*(feat\.?|ft\.?|featuring)\s+([^()]{2,100}?)\s*\)\s*$",
    flags=re.IGNORECASE,
)
_FORBIDDEN = re.compile(r"(?i)\b(?:live|remix|mix|demo|version|karaoke|cover)\b")


def canonical_explicit_artist_feature(artist):
    raw = str(artist or "").strip()
    m = _EXPLICIT_FEATURE.fullmatch(raw)
    if not m:
        return raw
    primary, marker, guest = (x.strip() for x in m.groups())
    if (not primary or not guest or _FORBIDDEN.search(guest)
            or re.search(r"\b(?:feat\.?|ft\.?|featuring)\s*$", primary, re.I)):
        return raw
    return f"{primary} feat. {guest}"


# Both titles are listed on the band's original 2014 album. Spotify credits
# the band solely as +/-; DO NOT generalize this punctuation-only artist name.
# https://plusminusnyc.bandcamp.com/album/jumping-the-tracks
# https://open.spotify.com/track/5UlVVjCUWsFfa2zqkT4lBs
_PLUSMINUS_TITLES = frozenset({"rewrite the story", "jumping the tracks"})


def verified_symbolic_plusminus(artist, title, catalog_artist, catalog_title, album):
    return (
        str(artist or "").strip().casefold() == "plusminus"
        and str(title or "").strip().casefold() in _PLUSMINUS_TITLES
        and str(catalog_artist or "").strip() == "+/-"
        and str(catalog_title or "").strip().casefold()
            == str(title or "").strip().casefold()
        and str(album or "").strip().casefold() == "jumping the tracks"
    )


# This is ONLY a search-ranking hint, not a validation rule.
# Both exact song/album combinations are independently source-confirmed.
# https://open.spotify.com/album/3Gqepup3SDauBRMULo8Pd8
# https://open.spotify.com/concert/4yv5FxJ2aMYbIZaxnBnvUw
_EXACT_CATALOG_ALBUM_HINTS = {
    ("isa and the filthy tongues", "jim's killer"): "Dark Passenger",
    ("bluhm", "midnight hill"): "Midnight Hill",
    ("plusminus", "rewrite the story"): "Jumping the Tracks",
    ("plusminus", "jumping the tracks"): "Jumping the Tracks",
}


def verified_report_album_hint(artist, title):
    return _EXACT_CATALOG_ALBUM_HINTS.get(
        (str(artist or "").strip().casefold(),
         str(title or "").strip().casefold())
    )


def verified_report_search_query(artist, title):
    album = verified_report_album_hint(artist, title)
    if not album:
        return None
    safe_title = str(title).replace('"', " ").strip()
    return f'track:"{safe_title}" album:"{album}"'
