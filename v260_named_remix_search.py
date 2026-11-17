"""v260: search-only rescue for a named remix on a LATER existing attempt.

Never approves an ordinary track: v243 and all normal matcher safety gates
must still accept the specific recording. No extra Spotify API requests.
"""
import re


def original_search_hint(artist, title, spotify_search_artist):
    """Return a focused original-title query or None if edition is uncertain."""
    raw = str(title or "").strip()
    m = re.fullmatch(
        r"(.+?)\s+\(([^()]+?)\s+(remix|mix)\)\s*",
        raw, flags=re.I,
    )
    if not m:
        return None
    base, remixer, _ = m.groups()
    # A named mix must have a clearly identified remixer; do not override
    # bare '(Remix)' or ordinary album/version/editorial suffixes.
    if not base.strip() or len(re.sub(r"[^a-z0-9]", "", base.casefold())) < 5:
        return None
    if not remixer.strip() or remixer.casefold() in {
        "original", "album", "single", "radio", "extended", "club",
    }:
        return None
    name = str(spotify_search_artist or "").replace('"', " ").strip()
    base = base.replace('"', " ").strip()
    if not name or not base:
        return None
    return f'{name} "{base}"'
