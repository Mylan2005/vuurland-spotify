"""Expliciete gebruikersuitsluitingen voor alle muziekaanvoerbronnen.

Geen detectie van etniciteit, nationaliteit of gezongen taal op basis van een
artiestennaam. Alleen gecontroleerde artiest-/trackidentiteiten; onbekende
alternatieve artiesten blijven toegelaten.
"""
import re
import unicodedata

from dark_edge_filter import DARK_EDGE_BLOCKED_ARTISTS

# Alleen duidelijk ongewenste mainstream pop / EDM uit de reeds bestaande
# Dark Edge uitsluitingen. Zwaardere rock/punk uit die lijst is eveneens
# uitgesloten volgens de bestaande muziekvoorkeur.
GLOBAL_EXCLUDED_ARTISTS = DARK_EDGE_BLOCKED_ARTISTS | frozenset({
    # Bekende J-/K-/C-pop-projecten die de gebruiker niet wil; dit is een
    # muziekselectie, geen gok naar de taal van onbekende artiesten.
    "bts", "blackpink", "twice", "stray kids", "newjeans", "aespa",
    "seventeen", "exo", "le sserafim", "ive", "itzy", "enhypen",
    "nct 127", "nct dream", "red velvet", "txt", "tomorrow x together",
    "jungkook", "jung kook", "jimin", "j-hope",
    "yoasobi", "ado", "kenshi yonezu", "official hige dandism",
    "fujii kaze", "king gnu", "aimyon", "radwimps",
    "jay chou", "g.e.m.", "gem tang",
})


def _identity(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def global_music_reject_reason(artist, title):
    """Afwijzen op exacte bekende identiteit; nooit substring of genre raden."""
    name = _identity(artist)
    if not name or not str(title or "").strip():
        return "artiest of titel ontbreekt"
    if name in GLOBAL_EXCLUDED_ARTISTS:
        return "expliciet uitgesloten pop-/dance-/andere artiest"
    # Gastartiesten: alleen expliciete 'feat', 'ft', 'featuring', 'with'.
    # Splits geen bestaande bandnamen met '&' of gewone woorden.
    credits = re.split(
        r"\s+(?:feat\.?|ft\.?|featuring|with)\s+",
        re.sub(r"\(\s*(?=(?:feat\.?|ft\.?|featuring|with)\s+)", " ", name),
        flags=re.IGNORECASE,
    )
    if any(part.strip(" ()[]") in GLOBAL_EXCLUDED_ARTISTS for part in credits):
        return "expliciet uitgesloten gastartiest"
    return None
