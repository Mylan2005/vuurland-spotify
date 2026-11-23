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
