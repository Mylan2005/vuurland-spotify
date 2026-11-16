"""v243: user-approved studio/original fallback after a requested remix.

A Spotify Search result is never proof of availability; this function only
allows the original recording on a *later* existing search strategy and only
when artist credits and full base title already match. The normal matcher
still enforces region, language, duplicates, ambiguity, and track safety.
"""
import re
import unicodedata


def _identity(value):
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", raw)


def safe_remix_original_fallback(*, requested_version, candidate_version,
                                 search_variant, primary_artist_exact,
                                 all_credits_present, requested_base,
                                 candidate_base):
    """Permit original/remaster, not a different remix, after exact remix search."""
    if int(search_variant or 0) < 1:
        return False
    if requested_version not in {"mix", "remix"}:
        return False
    if candidate_version not in {None, "original version", "album version",
                                 "single version", "remaster"}:
        return False
    if not primary_artist_exact or not all_credits_present:
        return False
    wanted = _identity(requested_base)
    found = _identity(candidate_base)
    return bool(wanted and len(wanted) >= 5 and wanted == found)
