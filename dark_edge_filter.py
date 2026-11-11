"""Dark Edge-bronfilter: laat onbekende ontdekkingen toe, zonder extra Spotify-calls.

Geen gesloten lijst met bekende artiesten: elk geldig nummer mag aan de normale
Vuurland-matcher worden aangeboden. Alleen persoonlijke artiestblokkades,
expliciet herkenbare Roemeenstalige opnames en eerdere specifieke uitsluitingen
blijven hier geblokkeerd. Dit is geen betrouwbare audio-taaldetectie:
RadioBox levert alleen artiest en titel.
"""
import re
import unicodedata

# Exacte volledige artiest of expliciete gast; nooit een substringfilter.
# Eerdere persoonlijke voorkeuren blijven behouden; Avicii is expliciet verboden.
DARK_EDGE_BLOCKED_ARTISTS = frozenset({"avicii", "dua lipa", "sam smith"})

# De opname van Coldplay heeft Avicii-productie, zonder een Avicii-artiestcredit.
# De twee bevestigde Roemeenstalige opnames blijven geweerd.
DARK_EDGE_BLOCKED_RECORDINGS = frozenset({
    ("coldplay", "a sky full of stars"),
    ("travka", "distante"),
    ("grimus", "priveste-ma"),
})

_ROMANIAN_TITLE_PATTERNS = (
    r"\b(?:culori\s+uitate|floare\s+de\s+maidan|povestea|iubirea|iubesc|dragostea|noaptea|sufletul|pastreaza|dezorientat|zilele|ploile|vantul)\b",
    r"\b(?:cea|cel)\s+mai\b",
    r"\bpriveste\s+ma\b",
    r"\b(?:nu|sa)\s+(?:mai|stiu|vreau|pot|pleci|iubesti)\b",
    r"\b(?:te|ma)\s+(?:iubesc|iubesti|astept|doare)\b",
    r"\b(?:inima|ochii|sufletul|viata|iubirea)\s+(?:mea|ta|noastra|tai)\b",
    r"\b(?:fara|langa|pana)\s+(?:tine|mine|noi|sfarsit)\b",
    r"\b(?:sat\s+dupa\s+sat|ploile\s+nu\s+vin|vantul)\b",
)


def _key(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.split())


def dark_edge_reject_reason(artist, title):
    """None = bronacceptatie; overige globale taal-/muziekregels gelden later."""
    a = _key(artist)
    t = _key(title)
    if not a or not t:
        return "lege artiest/titel"

    # Oudere opnames met accentverschillen en een Live-suffix eveneens weren.
    normalized_title = " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())
    if a == "grimus" and re.match(r"^priveste\s+ma(?:\b|$)", normalized_title):
        return "bevestigd Roemeenstalige opname"
    if (a, t) in DARK_EDGE_BLOCKED_RECORDINGS:
        return "expliciet uitgesloten opname"

    # Explicit feat./ft./featuring/with, also within parentheses.
    # 'Sam Smiths' is not 'Sam Smith' and may safely pass.
    credits = re.sub(r"\(\s*(?=(?:feat\.?|ft\.?|featuring|with)\s+)", " ", a)
    credited = [
        part.strip(" ()[]") for part in re.split(
            r"\s+(?:feat\.?|ft\.?|featuring|with)\s+|\s*(?:&|,)\s*", credits
        ) if part.strip(" ()[]")
    ]
    if a in DARK_EDGE_BLOCKED_ARTISTS or any(
        name in DARK_EDGE_BLOCKED_ARTISTS for name in credited
    ):
        return "expliciet uitgesloten artiest"

    normalized_title = unicodedata.normalize("NFKD", str(title).casefold())
    normalized_title = "".join(c for c in normalized_title if not unicodedata.combining(c))
    words = " ".join(re.sub(r"[^a-z0-9]+", " ", normalized_title).split())
    if any(re.search(pattern, words) for pattern in _ROMANIAN_TITLE_PATTERNS):
        return "herkenbaar Roemeenstalige titel"

    # Onbekende alternatieve artiesten mogen voortaan door deze bronpoort.
    # De centrale matcher/playlistfilters bepalen later of een nummer geschikt is.
    return None
