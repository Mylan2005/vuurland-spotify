"""v258 safe Spotify miss triage; diagnostics only, never approves a recording.

Only two consecutive *clearly unrelated* search results allow early parking.
An exact same-artist/base-title candidate rejected by existing guards is
reported for matcher review, without relaxing the guards.
"""
import re
import unicodedata


def _norm(value):
    s = unicodedata.normalize("NFKD", str(value or "").casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def _base_title(value):
    text = str(value or "").strip()
    # Named edits and remixes are removed only for diagnostic proximity,
    # NEVER used to allow an actual Spotify match.
    text = re.sub(
        r"\s*(?:\([^()]*\b(?:remix|mix|edit|remaster(?:ed)?|version)\b[^()]*\)"
        r"|\s+-\s+[^-]*\b(?:remix|mix|edit|remaster(?:ed)?|version)\b.*)$",
        "", text, flags=re.I,
    )
    return _norm(text)


def classify_candidates(artist, title, items):
    """Return ('weak'|'promising'|'uncertain', sanitized candidates).

    'weak' requires that NONE of the returned candidates matches either
    the exact artist or exact base title; fuzzy misses stay inconclusive.
    """
    if not isinstance(items, list):
        return "uncertain", []
    preview = []
    same_artist = False
    same_title = False
    both = False
    wanted_artist = _norm(artist)
    wanted_title = _base_title(title)
    for row in items[:10]:
        if not isinstance(row, dict):
            continue
        credits = row.get("artists", [])
        names = [
            str(a.get("name", "")) for a in credits
            if isinstance(a, dict) and a.get("name")
        ] if isinstance(credits, list) else []
        name = str(row.get("name", ""))[:200]
        artist_hit = bool(wanted_artist and any(_norm(x) == wanted_artist for x in names))
        title_hit = bool(wanted_title and _base_title(name) == wanted_title)
        same_artist |= artist_hit
        same_title |= title_hit
        both |= artist_hit and title_hit
        if len(preview) < 3:
            preview.append({
                "artist": ", ".join(names)[:180], "title": name,
                "spotify_id": str(row.get("id") or "")[:40],
            })
    if both:
        return "promising", preview
    if not same_artist and not same_title and wanted_artist and wanted_title:
        return "weak", preview
    return "uncertain", preview


def early_park_after_weak_results(previous_weak, current_kind, search_variant):
    """Fail closed; preserve first search AND one alternative search."""
    return bool(previous_weak and current_kind == "weak"
                and int(search_variant or 0) >= 1)


def record_miss(cache, key, source, artist, title, kind, preview, variant, *, max_entries=300):
    """Bounded, non-authorizing diagnostic history in existing cache."""
    ledger = cache.setdefault("__v258_matcher_triage", {})
    if not isinstance(ledger, dict):
        ledger = {}
        cache["__v258_matcher_triage"] = ledger
    ledger.pop(key, None)
    ledger[key] = {
        "source": source, "artist": artist, "title": title,
        "kind": kind, "variant": int(variant or 0),
        "candidates": preview[:3],
        "status": "review_guard" if kind == "promising" else
                  "low_relevance" if kind == "weak" else "uncertain",
    }
    while len(ledger) > max_entries:
        del ledger[next(iter(ledger))]
    return ledger[key]
