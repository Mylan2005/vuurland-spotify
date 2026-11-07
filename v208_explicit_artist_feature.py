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
