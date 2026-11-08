"""Conservatieve Dark Edge Radio-filter: geen externe APIs of Spotify-aanvragen.

Er is GEEN lijst meer met toegelaten artiesten: nieuwe indie-acts worden
niet afgewezen omdat ze onbekend zijn. Duidelijke commerciële hitparadepop is hier niet welkom; sfeervolle
alternatieve pop kan wel. Geen onbetrouwbare genre-inferentie uit alleen
RadioBox-tekst. Expliciet ongewenste artiesten, dance-/EDM-acts,
punk/metal en herkenbare ongewenste taal/titels worden geweerd.
Nederlands, Engels en Spaans mogen (bv. sfeervolle indie zoals Blanco White).
Genre en gezongen taal zijn met alleen RadioBox-metadata niet waterdicht vast te stellen.
"""

import re
import unicodedata

# Conservatieve, expliciete Dark Edge-bronpolicy: blokkeer herkenbare
# commerciële hitparadepop en club-/EDM-acts op basis van VOLLEDIGE artiest-
# of featuring-credits. Geen globale popban: bv. Gorillaz, Billie Eilish,
# Adele, Sia, Taylor Swift/Cardigan en onbekende alternatieve acts kunnen
# passend zijn. Geen genre-API, fuzzy substringverbod of Spotify-extra call.
# Exacte artiestnamen en expliciete featurings; overige bronnen ongemoeid.
DARK_EDGE_BLOCKED_ARTISTS = frozenset({
    # Persoonlijke uitsluiting.
    "dua lipa",
    # Expliciete gebruikerfeedback: Sam Smith past niet in Vuurland via Dark Edge.
    "sam smith",
    # Commerciële, duidelijk hitparadegerichte pop: uitsluitend Dark Edge.
    "ed sheeran", "justin bieber", "shawn mendes", "charlie puth",
    "maroon 5", "meghan trainor", "katy perry", "ariana grande",
    "kylie minogue", "britney spears", "backstreet boys",
    "one direction", "jonas brothers", "selena gomez",
    "camila cabello", "jason derulo", "harry styles",
    "ava max", "bebe rexha", "zara larsson", "rita ora",
    "sabrina carpenter", "tate mcrae", "bruno mars",
    "lewis capaldi", "james arthur", "benson boone",

    # Dance, EDM en mainstream festival-/club-DJ's.
    "afrojack", "alan walker", "alesso", "armin van buuren",
    "avicii", "axwell", "calvin harris", "david guetta",
    "deadmau5", "diplo", "dj snake", "don diablo", "fisher",
    "galantis", "hardwell", "ingrosso", "kleerup", "kygo",
    "lost frequencies", "major lazer", "marshmello",
    "martin garrix", "meduza", "robin schulz", "sigala",
    "skrillex", "steve aoki", "swedish house mafia",
    "the chainsmokers", "tiesto", "zedd",
    # Punk, nu-metal en zware rock die niet bij de playlist passen.
    "blink-182", "bring me the horizon", "faith no more",
    "fall out boy", "five finger death punch", "green day",
    "limp bizkit", "linkin park", "metallica", "megadeth",
    "papa roach", "pantera", "rammstein", "slipknot",
    "sum 41", "system of a down", "the offspring", "volbeat",
})

# Enkel expliciet ongewenste nummers uitsluiten, niet het hele
# (mogelijk popgerichte) oeuvre van een artiest. Avicii's productie
# bij 'A Sky Full of Stars' is een uitgesproken dance/EDM-uitzondering.
DARK_EDGE_BLOCKED_RECORDINGS = frozenset({
    ("coldplay", "a sky full of stars"),
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
    # Spaans wordt niet meer geweerd: o.a. Blanco White, Spaanse indie/folk.
    # Duitse zang blijft wél uitgesloten door de bestaande beschermingschecks.
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
    daarnaast verplicht. Nederlands, Engels én Spaans zijn toegestaan.
    De werkelijk gezongen taal blijkt niet betrouwbaar uit RadioBox-metadata.
    """
    a = _key(artist)
    raw = str(title or "").strip()
    t = _key(raw)
    if not a or not t:
        return "lege artiest/titel"
    # Exacte artiest en expliciet gecrediteerde gasten; GEEN substring-ban
    # (bv. 'sia' mag nooit een deel van een andere artiestnaam raken).
    # Parenthesized guests are also mandatory: "Kim Petras (feat. Sam
    # Smith)" must not slip through the Dark Edge gate. Only parenthesized
    # explicit credit markers are unwrapped, never arbitrary parentheses.
    credit_text = re.sub(
        r"\(\s*(?=(?:feat\.?|ft\.?|featuring|with)\s+)", " ", a
    )
    credited = [part.strip(" ()[]") for part in re.split(
        r"\s+(?:feat\.?|ft\.?|featuring|with)\s+|\s*(?:&|,)\s*", credit_text
    )]
    if a in DARK_EDGE_BLOCKED_ARTISTS or any(
        name.strip() in DARK_EDGE_BLOCKED_ARTISTS for name in credited
    ):
        return "geblokkeerde dance-/EDM-, punk-/metalartiest of persoonlijke uitzondering"
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
