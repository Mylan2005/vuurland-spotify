"""Conservatieve Dark Edge Radio-filter: geen externe APIs of Spotify-aanvragen.

Dit is een TOELATINGSLIJST voor hoofdzakelijk Engelstalige indie-/alternatieve
artiesten, geen automatische herkenning van gezongen taal. Een Engelse titel
bewijst niet dat de tekst Engels is. Onbekende artiesten vallen af.
"""

import re
import unicodedata

# Alleen expliciete artiestidentiteiten; GEEN fuzzy of substring match.
# Bewust geen algemene pop-, metal-, punk- of meertalige artiesten.
DARK_EDGE_APPROVED_ARTISTS = frozenset({
    "alt-j", "arcade fire", "arctic monkeys",
    "austra", "band of horses", "beach house", "beck", "ben howard",
    "bloc party", "blur", "bombay bicycle club", "cage the elephant",
    "cigarettes after sex", "death cab for cutie", "depeche mode",
    "diiv", "doves", "elbow", "editors", "eels", "father john misty",
    "fink", "florence + the machine", "florence and the machine",
    "foals", "fontaines d.c.", "fontaines dc", "future islands",
    "garbage", "glass animals", "goth babe", "grizzly bear",
    "hooverphonic", "interpol", "jake bugg", "joy division",
    "kasabian", "keane", "kings of leon", "london grammar", "low",
    "m83", "massive attack", "mgmt", "muse", "new order",
    "nothing but thieves", "oasis", "of monsters and men",
    "phoebe bridgers", "pj harvey", "placebo", "portishead",
    "pulp", "radiohead", "r.e.m.", "royal blood", "silversun pickups",
    "slowdive", "snow patrol", "sonic youth", "spoon", "suede",
    "tame impala", "the black keys", "the cure", "the killers",
    "the kooks", "the national", "the neighbourhood",
    "the smashing pumpkins", "the strokes", "the verve",
    "the war on drugs", "the xx", "tori amos", "two door cinema club",
    "vampire weekend", "white lies", "wolf alice",
    "yard act", "young the giant",
})

# Alleen duidelijke meertalige zinsdelen, niet korte ambigue woorden als
# "no", "in", "la" of "die". Deze lijst is extra controle, geen taalbewijs.
_NON_ENGLISH_PHRASES = (
    # Roemeens
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
    r"\b(?:ti\s+amo|io\s+(?:sono|voglio)|senza\s+te|per\s+sempre|il\s+mio|la\s+mia|eu\s+(?:sou|quero)|nao\s+(?:sei|quero)|meu\s+amor|voce\s+e)\b",
    # Nederlands
    r"\b(?:ik\s+(?:ben|wil|hou|weet)|jij\s+(?:bent|weet)|mijn\s+(?:hart|liefde|leven)|zonder\s+jou|met\s+jou|voor\s+altijd)\b",
)

# Opnames met een vreemde taal kunnen ook een Engelse titel hebben.
# Exacte bekende uitzonderingen zijn steeds expliciet te blokkeren.
DARK_EDGE_BLOCKED_RECORDINGS = frozenset()  # Alleen bevestigde, specifiek ongewenste opnames toevoegen.


def _key(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def dark_edge_reject_reason(artist, title):
    """None = door de voorlopige bronfilter; anders de afwijsreden.

    De bestaande globale matcher, taal-, regio- en duplicaatchecks blijven
    daarnaast verplicht. Ook een toegelaten track is niet gegarandeerd Engels
    gezongen: RadioBox en Spotify geven geen verifieerbare zangtaalmetadata.
    """
    a = _key(artist)
    raw = str(title or "").strip()
    t = _key(raw)
    if not a or not t:
        return "lege artiest/titel"
    if a not in DARK_EDGE_APPROVED_ARTISTS:
        return "artiest niet op de conservatieve indie-toelatingslijst"
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
