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
    return " ".join(raw.casefold().split()) in names


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
