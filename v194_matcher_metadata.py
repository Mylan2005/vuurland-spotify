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
    """Verwijder alleen exact de volledige herhaalde artiestnaam NA de titel.

    'Birkii — Holy War - Birkii' -> 'Holy War'.
    'Aerial Love Feed — Someone' blijft 'Someone' (niet 'Someone New').
    """
    raw = str(title or "").strip()
    parts = re.fullmatch(r"(.+?)\s+[-–—]\s+(.+)", raw)
    if parts and _words(parts.group(2)) == _words(artist) and parts.group(1).strip():
        return parts.group(1).strip()
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
