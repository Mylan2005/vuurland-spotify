"""v245: safely split two explicit multiword guest credits in RadioBox titles.

Some sources write "Trust ft. Tom Hodge & Kathrin deBoer" while Spotify
returns separate artist objects. We split only clearly delimited two-person
credits; ambiguous groups remain whole. The main matcher still checks that
*each* requested featured artist appears in the Spotify artist objects.
"""
import re


def split_explicit_multiword_guests(guest_text):
    raw = " ".join(str(guest_text or "").strip().split())
    if not raw:
        return []
    # Only a single explicit joiner; avoid guessing band/project names.
    parts = re.split(r"\s+(?:&|and)\s+", raw, flags=re.IGNORECASE)
    if (len(parts) == 2
            and all(len(p.split()) >= 2 for p in parts)
            and all(re.fullmatch(r"[\w.'’\- ]+", p, flags=re.UNICODE)
                    for p in parts)):
        return parts
    return [raw]
