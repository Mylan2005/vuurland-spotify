"""Safe generic RadioBox search-metadata repair (v261).

This module never approves Spotify tracks. All candidate, guest, version,
region and duplicate guards remain in vuurland_sync.py.
"""
import re

_ABBREVIATED_FEATURE = re.compile(
    r"^(.+?)\s+\(\s*f\.?\s+([A-Za-z][^()\[\]]{1,79}?)\s*\)\s*$",
    flags=re.IGNORECASE,
)

def abbreviated_title_feature(title):
    """Parse explicit (f Name) as a REQUIRED guest, not a version or fuzzy match."""
    raw = str(title or "").strip()
    match = _ABBREVIATED_FEATURE.fullmatch(raw)
    if not match:
        return None
    song, guest = match.group(1).strip(), match.group(2).strip()
    if not song or len(guest) < 2:
        return None
    if re.search(r"\b(?:remix|mix|live|version|cover|demo)\b", guest, re.I):
        return None
    return song, guest

def safe_contraction_replacement(original_token, proposed):
    """Ill is a complete English adjective, not necessarily I'll."""
    if str(original_token or "").casefold().strip() == "ill":
        return None
    return proposed

def verified_daze_album_alias(title, candidate):
    """DA/ZE -> Daze requires independently known song AND split-album credit.

    DAZE is a short, non-unique name. Never infer all songs by every artist
    called Daze belong to the RadioBox shoegaze project.
    """
    if str(title or "").strip().casefold() != "mellow":
        return False
    if not isinstance(candidate, dict):
        return False
    album = str((candidate.get("album") or {}).get("name") or "").casefold()
    album_words = " ".join(re.findall(r"[a-z0-9]+", album))
    return album_words == "da ze glia split"


def exact_single_x_project_credit(source_artist, catalog_artist_names):
    """Accept a literal full 'A x B' project as ONE catalog artist.

    Some official Spotify artist profiles use the exact full project credit
    instead of separate A and B artist objects. This must NEVER accept an
    A-only or B-only release, reordered artists, fuzzy names, or extra artists.
    All title/version/market checks are performed by the calling matcher.
    """
    radio = " ".join(str(source_artist or "").strip().split())
    match = re.fullmatch(r"(.{2,}?)\s+x\s+(.{2,}?)", radio)
    if not match or not isinstance(catalog_artist_names, (tuple, list)):
        return False
    if len(catalog_artist_names) != 1:
        return False
    catalog = " ".join(str(catalog_artist_names[0] or "").strip().split())
    return bool(catalog and catalog.casefold() == radio.casefold())


def equivalent_catalog_connector_title(source_title, catalog_title):
    """Exact title words with only typographic 'and' / 'n' and OK/Okay variance.

    Strictly a full-title comparison. Edition/version markers are never
    removed here; original candidate gates still enforce versions.
    Neither arbitrary word spelling corrections nor title prefixes qualify.
    """
    def words(value):
        raw = str(value or "").casefold().replace("’", "'")
        # Only apostrophe-marked 'N' is shorthand for and. A bare N may
        # be a meaningful letter in a song title and must stay distinct.
        raw = re.sub(r"(?<![a-z0-9])'n'(?![a-z0-9])", " _and_ ", raw)
        tokens = re.findall(r"_and_|[a-z0-9]+", raw)
        if not tokens:
            return ()
        return tuple(
            "and" if word == "_and_" else "ok" if word == "okay" else word
            for word in tokens
        )
    left, right = words(source_title), words(catalog_title)
    # Avoid accepting a one-word coincidence or punctuation-only title.
    return bool(len(left) >= 2 and left == right
                and str(source_title or "").casefold().strip()
                    != str(catalog_title or "").casefold().strip())


def equivalent_leading_number_artist(requested, catalog):
    """Same FULL artist credit with a leading 0-20 number written in words.

    Never accept a partial artist name, a different number, a trailing
    credit change, or a fuzzy match. For one complete artist object only.
    This is ONLY artist metadata, not song/edition/playlist approval.
    """
    numbers = (
        "zero", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "eleven", "twelve", "thirteen",
        "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen", "twenty",
    )
    def identity(value):
        raw = str(value or "").casefold().strip()
        tokens = re.findall(r"[a-z0-9]+", raw)
        if len(tokens) < 3:
            return None
        first = tokens[0]
        if first.isdigit() and int(first) <= 20:
            first = numbers[int(first)]
        if first not in numbers:
            return None
        # Remaining words must be complete, unchanged proper-name tokens.
        return (first, tuple(tokens[1:]))
    left, right = identity(requested), identity(catalog)
    return bool(left and right and left == right
                and str(requested or "").casefold().strip()
                    != str(catalog or "").casefold().strip())
