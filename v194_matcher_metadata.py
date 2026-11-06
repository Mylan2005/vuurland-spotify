"""v194: algemene, conservatieve metadatarescue uit 12 matcher-rapporten.

Geen fuzzy titelmatch, geen Spotify-netwerk, geen ongeteste URI-mappings.
Alleen expliciete afgebakende bronmetadata en volledige artiest-credits.
"""
import re
import unicodedata


def _words(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.findall(r"[^\W_]+", value, re.UNICODE)


def canonical_artist(artist):
    """'Decemberists, The' = 'The Decemberists', niet algemene omzetting."""
    raw = str(artist or "").strip()
    match = re.fullmatch(r"(.{3,}?),\s*the", raw, flags=re.IGNORECASE)
    return "The " + match.group(1).strip() if match else raw


def artist_join_key(artist):
    """Alleen dezelfde VOLLEDIGE artiestwoorden en and/&/+ connector."""
    raw = canonical_artist(artist)
    raw = re.sub(r"\s*(?:&|\+)\s*", " and ", raw)
    raw = re.sub(r"\s+and\s+", " and ", raw, flags=re.IGNORECASE)
    return " ".join(_words(raw))


def canonical_title(artist, title):
    """Remove an EXACT repeated full artist credit from the end of a song title.

    Radio feeds may write 'Holy War - Birkii', 'A - B - Artist' or
    'A—Artist'. Only a complete final credit matching the provided artist
    can be removed. Never remove an unmatched guest, mix or version suffix.
    Ordinary '-' must have spaces on BOTH sides to avoid splitting words.
    """
    raw = str(title or "").strip()
    artist_words = _words(artist)
    if not raw or not artist_words:
        return raw

    # Em/en dashes are unambiguous separators even without spaces; a normal
    # hyphen only counts with surrounding whitespace.
    separators = list(re.finditer(r"\s+[-–—]\s+|\s*[–—]\s*", raw))
    for match in reversed(separators):
        prefix = raw[:match.start()].strip()
        suffix = raw[match.end():].strip()
        if prefix and suffix and _words(suffix) == artist_words:
            return prefix
    return raw

def normalize_explicit_version(title):
    """Eenzelfde label inkorten in bronmetadata mag zoekranking niet breken.

    Alleen 'Ext. Version' -> 'Extended Version'; een andere mix of live-versie
    wordt NOOIT automatisch een studio-opname.
    """
    raw = str(title or "")
    return re.sub(r"(?i)\bext\.\s+version\b", "Extended Version", raw)


def clearly_truncated_final_word(requested, candidate):
    """Een uitzonderlijk duidelijke onafgewerkte frase compleet maken.

    Minstens zes exacte woorden, bron eindigt op een functie-/bezitswoord,
    Spotify voegt slechts EEN volledig woord toe. De aanroeper vereist
    daarnaast een exacte hoofdartiest en dezelfde uitvoeringsversie.
    Geen vrije gedeeltelijke of fuzzy match.
    """
    left, right = _words(requested), _words(candidate)
    return bool(
        len(left) >= 6
        and len(right) == len(left) + 1
        and left[-1] in {"my", "your", "our", "the", "a", "an", "of"}
        and left == right[:-1]
        and len(right[-1]) >= 3
    )
