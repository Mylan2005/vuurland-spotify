"""v241: conservative end-of-title singular/plural recovery for radio metadata.

A search hint is never an accepted recording. The matching layer separately
requires exact primary artist, all explicit featured artist credits, compatible
version, region, exclusions and other guards.
"""
import re
import unicodedata


def _words(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold().strip())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


def _full_stem_and_last(value):
    words = _words(value)
    if len(words) < 3 or len("".join(words)) < 16:
        return None
    if len(words[-1]) < 5 or not words[-1].isalpha():
        return None
    return words[:-1], words[-1]


def final_s_candidate_title(title):
    """Only a search hint; query a plausible plural on retry, never approve it.

    Do not alter explicit version, cover, mix, or guest qualifiers.
    """
    raw = str(title or "").strip()
    if re.search(r"(?i)\b(feat\.?|ft\.?|featuring|remix|mix|live|cover|version|extended|edit|demo)\b", raw):
        return None
    parsed = _full_stem_and_last(raw)
    if not parsed:
        return None
    _, last = parsed
    if last.endswith("s") or last.endswith("x") or last.endswith("z"):
        return None
    return raw + "s"


def safe_final_plural_equivalent(requested_base, catalog_base, *,
                                  primary_artist_exact, all_credits_present,
                                  wanted_version, catalog_version):
    """Equal whole title except ONE last 's'; no fuzzy search or credit bypass."""
    if (not primary_artist_exact or not all_credits_present
            or wanted_version != catalog_version):
        return False
    left = _full_stem_and_last(requested_base)
    right = _full_stem_and_last(catalog_base)
    if not left or not right or left[0] != right[0]:
        return False
    a, b = left[1], right[1]
    shorter, longer = sorted((a, b), key=len)
    return bool(
        shorter and len(shorter) >= 5 and len(longer) == len(shorter) + 1
        and not shorter.endswith("s") and longer == shorter + "s"
    )
