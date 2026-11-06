"""v200: strict, artist-bound known catalog title variants.

No free word insertion, fuzzy equivalence, catalog URI mappings, or Spotify
calls. A candidate still needs the exact primary artist, version and all
existing matcher safety checks.
"""
import re
import unicodedata


def _identity(text):
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


# Both official Spotify and Apple Music catalogues use the full title below.
# Radio metadata from a real run contained the shorter title.
_VERIFIED = {
    ("tired pony", "all things at once"): "all things all at once",
}


def verified_catalog_title(artist, requested, candidate):
    """Only exact confirmed artist + exact reported title + official title."""
    artist_key = _identity(artist)
    requested_key = _identity(requested)
    catalog = _VERIFIED.get((artist_key, requested_key))
    return bool(catalog and _identity(candidate) == catalog)
