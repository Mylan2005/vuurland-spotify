"""Owner-approved exact Cure title correction and ordinary-version mix policy.

These substitutions change ONLY the Spotify matching title; original radio
artist/title, FIFO entry, source identity and cache key stay unchanged.
"""
import re


def owner_approved_album_version(artist, title):
    """For The Cure, correct Play and use ordinary releases for named mixes."""
    if str(artist or "").strip().casefold() != "the cure":
        return title
    raw = str(title or "").strip()
    if raw.casefold() == "play":
        return "Play for Today"
    # Only an explicitly separated version suffix is removable. Never strip
    # a song whose core title itself happens to contain the word 'mix'.
    match = re.fullmatch(
        r"(.+?)\s*(?:\(([^()]*)\)|\[([^\[\]]*)\]|\s+[-–—]\s+(.+))\s*",
        raw,
    )
    if match:
        base = match.group(1).strip()
        suffix = next((part for part in match.groups()[1:] if part is not None), "")
        if (re.search(r"\bmix\b", suffix, flags=re.IGNORECASE)
                and not re.search(r"\b(?:live|acoustic|demo|instrumental)\b",
                                  suffix, flags=re.IGNORECASE)):
            return base
    return title
