"""Conservatieve Dark Edge Radio-filter: geen externe APIs of Spotify-aanvragen.

Er is GEEN lijst meer met toegelaten artiesten: nieuwe indie-acts worden
niet afgewezen omdat ze onbekend zijn. Wel weigeren we duidelijk ongewenste
pop-, punk- en metalartiesten en herkenbare anderstalige titels.
Nederlands en Engels mogen. Genre en gezongen taal zijn met alleen
RadioBox-metadata niet waterdicht vast te stellen.
"""

import re
import unicodedata

# Dit is uitsluitend een AFWIJSLIJST voor bekende, duidelijk niet-gewenste
# pop-/dance-/punk-/metalacts. Nieuwe indie- en alternative-artiesten krijgen
# normaal toegang zonder voorafgaande individuele goedkeuring.
# Bij twijfel over een act niet automatisch op basis van naam of land blokkeren.
DARK_EDGE_BLOCKED_ARTISTS = frozenset({
    # Commerciele hitpop, urbanpop en dance uit o.a. RadioBox-historie.
    "ariana grande", "avicii", "bebe rexha", "beyonce", "billie eilish",
    "black eyed peas", "bruno mars", "calvin harris", "camila cabello",
    "charlie puth", "david guetta", "doja cat", "drake", "dua lipa",
    "ed sheeran", "ellie goulding", "james blunt", "jason derulo",
    "justin bieber", "katy perry", "kendrick lamar", "kleerup",
    "kylie minogue", "lady gaga", "lily allen", "major lazer",
    "maroon 5", "miley cyrus", "nicki minaj", "one direction",
    "rihanna", "robin thicke", "robyn", "sam smith", "selena gomez",
    "sia", "taylor swift", "the weeknd", "the chainsmokers",
    "tom odell", "usher", "zara larsson",
    # Punk, nu-metal en expliciet ongewenste stevige bands.
    "blink-182", "bring me the horizon", "fall out boy", "five finger death punch",
    "green day", "limp bizkit", "linkin park", "metallica", "megadeth",
    "papa roach", "pantera", "rammstein", "slipknot", "sum 41",
    "system of a down", "the offspring", "volbeat",
})

# Specifieke bekende mainstream-popsongs van verder gemengde rockbands
# kunnen worden uitgesloten zonder hun hele oeuvre te blokkeren.
DARK_EDGE_BLOCKED_RECORDINGS = frozenset({
    ("coldplay", "a sky full of stars"),
    ("coldplay", "my universe"),
    ("coldplay", "higher power"),
    ("travka", "distante"),  # Bevestigde anderstalige titel uit de radiogeschiedenis.
})

# Alleen duidelijke meertalige zinsdelen, niet korte ambigue woorden als
# "no", "in", "la" of "die". Deze lijst is extra controle, geen taalbewijs.
_NON_ENGLISH_PHRASES = (
    # Roemeens (ook enkele onderscheidende losse woorden/frasen)
    r"\b(?:culori\s+uitate|floare\s+de\s+maidan|povestea|iubirea|iubesc|dragostea|noaptea|sufletul|pastreaza|dezorientat|zilele|ploile|vantul)\b",
    r"\b(?:cea|cel)\s+mai\b",
    r"\b(?:nu|sa)\s+(?:mai|stiu|vreau|pot|plec|pleci|iubesc|iubesti)\b",
    r"\b(?:te|ma)\s+(?:iubesc|iubesti|astept|doare)\b",
    r"\b(?:inima|ochii|sufletul|viata|iubirea)\s+(?:mea|ta|noastra|tai)\b",
    r"\b(?:fara|langa|pana)\s+(?:tine|mine|noi|sfarsit)\b",
    r"\b(?:sat\s+dupa\s+sat|ploile\s+nu\s+vin|vantul)\b",
    # Duits
    r"\b(?:ich|du|wir)\s+(?:bin|bist|sind|liebe|habe|will|weiss|vermiss|vermisse)\b",
    r"\b(?:mein|meine|dein|deine)\s+(?:herz|liebe|leben|welt)\b",
    r"\b(?:ohne|fuer|fur)\s+(?:dich|mich|uns|euch)\b",
    # Frans
    r"\b(?:je|tu|nous|vous)\s+(?:suis|veux|sais|sommes|aime|t\s+aime|es|etes)\b",
    r"\b(?:c\s+est|j\s+ai|l\s+amour|mon\s+coeur|sans\s+toi|pour\s+toi|avec\s+toi|au\s+revoir)\b",
    # Spaans
    r"\b(?:te\s+quiero|no\s+te|yo\s+(?:soy|quiero|tengo)|mi\s+corazon|sin\s+ti|la\s+vida|el\s+amor|me\s+gusta|buenas\s+noches)\b",
    r"\b(?:selva\s+y\s+mar|para\s+ti|por\s+que)\b",
    # Italiaans/Portugees
    r"\b(?:ti\s+(?:amo|voglio)|io\s+(?:sono|voglio)|senza\s+te|per\s+sempre|il\s+mio|la\s+mia|eu\s+(?:sou|quero)|nao\s+(?:sei|quero)|meu\s+amor|voce\s+e)\b",
)

def _key(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.split())


def dark_edge_reject_reason(artist, title):
    """None = door de voorlopige bronfilter; anders de afwijsreden.

    De bestaande globale matcher, taal-, regio- en duplicaatchecks blijven
    daarnaast verplicht. Nederlands én Engels zijn toegestaan. De toegelaten
    track is niet bewezen Engels/Nederlands gezongen; zulke metadata ontbreken.
    """
    a = _key(artist)
    raw = str(title or "").strip()
    t = _key(raw)
    if not a or not t:
        return "lege artiest/titel"
    # Exacte artiest en expliciet gecrediteerde gasten; GEEN substring-ban
    # (bv. 'sia' mag nooit een deel van een andere artiestnaam raken).
    credited = re.split(r"\s+(?:feat\.?|ft\.?|featuring|with)\s+|\s*(?:&|,)\s*", a)
    if a in DARK_EDGE_BLOCKED_ARTISTS or any(
        name.strip() in DARK_EDGE_BLOCKED_ARTISTS for name in credited
    ):
        return "expliciet ongewenste pop-, punk- of metalartiest"
    if (a, t) in DARK_EDGE_BLOCKED_RECORDINGS:
        return "expliciet uitgesloten opname"
    # Geen Griekse/Cyrillische/Arabische/CJK-tekens in titels.
    if any(ch.isalpha() and "LATIN" not in unicodedata.name(ch, "")
           for ch in raw):
        return "niet-Latijns schrift"
    normalized = unicodedata.normalize("NFKD", raw.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    words = " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())
    if any(re.search(pattern, words) for pattern in _NON_ENGLISH_PHRASES):
        return "duidelijk anderstalige titel"
    return None
