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
