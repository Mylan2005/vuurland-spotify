"""Dark Edge-bronfilter: laat onbekende ontdekkingen toe, zonder extra Spotify-calls.

Geen gesloten lijst met goedgekeurde artiesten. Wel exact de 36 door de
gebruiker beoordeelde tracks, acht uitgesloten artiesten inclusief Avicii,
en duidelijke Roemeenstalige titels weren. Dit is geen audio-taaldetectie:
RadioBox levert alleen artiest en titel. Andere bronnen blijven onaangeroerd.
"""
import re
import unicodedata

# Exacte volledige artiest of expliciete gast; nooit een substringfilter.
# Zeven door de gebruiker bevestigde pop-/danceartiesten én Avicii.
# Alleen Dark Edge: de algemene uitsluitingen van andere bronnen wijzigen niet.
DARK_EDGE_BLOCKED_ARTISTS = frozenset({
    "avicii", "disclosure", "the chemical brothers", "tones and i",
    "sam smith", "dua lipa", "oakenfold", "paul oakenfold", "kylie minogue",
})

# Exacte gebruikerkeuzes uit de zes Dark Edge-weekoverzichten (11-11-2026).
# Bewaar artiest én titel; geen algemeen genreverbod of landfilter.
# Schrijfvarianten (accenten, leestekens, spatiering) worden genormaliseerd.
DARK_EDGE_USER_BLOCKED_TRACKS = (
    ("Alexandru Andrieș", "Cea mai frumoasa zi"),
    ("Byron", "Granița-n răniță"),
    ("Eyedrops", "Culori Uitate"),
    ("Eyedrops", "Păstrează-mi calmul"),
    ("Firma", "Două suflete"),
    ("Grimus", "Privește-mă"),
    ("Jurjak", "Inima de piatră"),
    ("Jurjak", "Vântul"),
    ("Kumm", "Să Nu Spui Nimănui"),
    ("Omul cu Șobolani", "(dez)Orientat"),
    ("Omul cu Șobolani vs. Michi", "Dezorientat"),
    ("Robin and the Backstabbers", "Muzica în cântece"),
    ("Robin and the Backstabbers", "Sat După Sat"),
    ("Robin and the Backstabbers", "Soare Cu Dinți"),
    ("Robin and the Backstabbers", "Vânătoarea Regală"),
    ("Snails", "Nu-mi pasă"),
    ("Șuie Paparude", "Cea mai bună zi"),
    ("The Mono Jacks", "Un sfert de secundă"),
    ("Toulouse Lautrec", "Te spun"),
    ("Travka", "Soare răsare"),
    ("Urma", "Cine iubește și lasă"),
    ("Vita de Vie", "Haihui"),
    ("Vita de Vie", "Varză"),
    ("Gojira & Planet H feat. Robin", "Regele Verii"),
    ("Alternosfera", "Muta"),
    ("Ana Coman", "Contratimp"),
    ("Eyedrops", "Bicicleta"),
    ("Kumm", "Morsa"),
    ("The Mono Jacks", "Drumul"),
    ("Disclosure feat. Eliza Doolittle", "You & Me (Flume remix)"),
    ("The Chemical Brothers", "Hey Boy Hey Girl"),
    ("Tones and I", "Dance Monkey"),
    ("Sam Smith", "Too Good at Goodbyes"),
    ("Dua Lipa", "Be The One"),
    ("Oakenfold", "Starry Eyed Surprise"),
    ("Kylie Minogue", "I Believe in You (Mylo Vocal Mix)"),
)


# Bevestigd Roemeenstalige opnames blijven geweerd.
DARK_EDGE_BLOCKED_RECORDINGS = frozenset({
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


def _song_key(value):
    # Titelvergelijking; verwijder zero-width tekens en onschuldige interpunctie.
    value = _key(value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


DARK_EDGE_USER_BLOCKED_KEYS = frozenset(
    (_song_key(artist), _song_key(title))
    for artist, title in DARK_EDGE_USER_BLOCKED_TRACKS
)


def _is_user_blocked_track(artist, title):
    a, t = _song_key(artist), _song_key(title)
    if (a, t) in DARK_EDGE_USER_BLOCKED_KEYS:
        return True
    # Met of zonder een expliciete versieaanduiding zoals (Live)/(Remaster).
    # Alleen voor de exacte uitgesloten track; geen andere liedjes blokkeren.
    if a == "grimus" and re.match(r"^priveste ma(?:\\b|$)", t):
        return True
    if a in ("omul cu sobolani", "omul cu sobolani vs michi") and re.match(
        r"^(?:dez orientat|dezorientat)(?:\\b|$)", t
    ):
        return True
    return False


def dark_edge_reject_reason(artist, title):
    """None = bronacceptatie; overige globale taal-/muziekregels gelden later."""
    a = _key(artist)
    t = _key(title)
    if not a or not t:
        return "lege artiest/titel"
    if _is_user_blocked_track(artist, title):
        return "gebruikerskeuze: expliciet uitgesloten Dark Edge-opname"


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
        # Behoud het bestaande redenlabel: Duysters archiefpoort en offline
        # regressies herkennen dit letterlijk. Geen Duyster-gedrag wijzigen.
        return "geblokkeerde dance-/EDM-, punk-/metalartiest of persoonlijke uitzondering"

    normalized_title = unicodedata.normalize("NFKD", str(title).casefold())
    normalized_title = "".join(c for c in normalized_title if not unicodedata.combining(c))
    words = " ".join(re.sub(r"[^a-z0-9]+", " ", normalized_title).split())
    if any(re.search(pattern, words) for pattern in _ROMANIAN_TITLE_PATTERNS):
        return "herkenbaar Roemeenstalige titel"

    # Onbekende alternatieve artiesten mogen voortaan door deze bronpoort.
    # De centrale matcher/playlistfilters bepalen later of een nummer geschikt is.
    return None
