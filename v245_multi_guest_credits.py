"""v245: safely split two explicit multiword guest credits in RadioBox titles.

Some sources write "Trust ft. Tom Hodge & Kathrin deBoer" while Spotify
returns separate artist objects. We split only clearly delimited two-person
credits; ambiguous groups remain whole. The main matcher still checks that
*each* requested featured artist appears in the Spotify artist objects.
"""
import re


def guest_credit_matches(requested, spotify_names):
    """Resolve explicitly ellipsized final guest using full Spotify artist objects."""
    raw = str(requested or "").strip()
    names = [" ".join(str(n).casefold().split()) for n in spotify_names]
    if raw.endswith(("...", "…")):
        prefix = raw[:-3].strip() if raw.endswith("...") else raw[:-1].strip()
        prefix = " ".join(prefix.casefold().split())
        if len(prefix) < 10 or len(prefix.split()) < 2:
            return False
        matches = [name for name in names if name.startswith(prefix + " ")]
        return len(set(matches)) == 1
    normalized = " ".join(raw.casefold().split())
    if normalized in names:
        return True
    # A named pair is only valid if BOTH full credits occur as distinct
    # Spotify artist objects, not by fuzzy similarity.
    parts = re.split(r"\s+(?:&|and)\s+", normalized)
    return (len(parts) == 2 and all(len(p) >= 4 for p in parts)
            and len(set(parts)) == 2 and all(p in names for p in parts))


def split_explicit_multiword_guests(guest_text):
    raw = " ".join(str(guest_text or "").strip().split())
    if not raw:
        return []
    # Commas inside an explicit guest field separate artists; keep & in band names.
    if "," in raw:
        parts = [p.strip() for p in raw.split(",")]
        if (2 <= len(parts) <= 6 and all(parts)
                and all(len(p) >= 2 for p in parts)):
            return parts
        return [raw]
    parts = re.split(r"\s+(?:&|and)\s+", raw, flags=re.IGNORECASE)
    if (len(parts) == 2
            and all(len(p.split()) >= 2 for p in parts)
            and all(re.fullmatch(r"[\w.'’\- ]+", p, flags=re.UNICODE)
                    for p in parts)):
        return parts
    return [raw]


def split_full_collaborator_credit(credit):
    """Split unambiguous 3+ artist lists; preserve regular band names."""
    raw = " ".join(str(credit or "").strip().split())
    segments = [p.strip() for p in raw.split(",")]
    if len(segments) < 3 or len(segments) > 8:
        return []
    if re.search(r"\s+(?:&|and)\s+", segments[-1], re.I):
        tail = re.split(r"\s+(?:&|and)\s+", segments[-1], maxsplit=1, flags=re.I)
        segments = segments[:-1] + tail
    if (not all(len(p) >= 4 and re.search(r"[A-Za-z]", p) for p in segments)
            or len({p.casefold() for p in segments}) != len(segments)):
        return []
    return segments


def complete_collaboration_matches(requested, spotify_names):
    """Each complete artist must appear exactly as a Spotify artist object."""
    parts = split_full_collaborator_credit(requested)
    if not parts:
        return False
    expected = {" ".join(p.casefold().split()) for p in parts}
    actual = {" ".join(str(n).casefold().split()) for n in spotify_names}
    return expected == actual
