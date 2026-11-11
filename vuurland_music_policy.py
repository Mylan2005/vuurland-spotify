"""Expliciete gebruikersuitsluitingen voor alle muziekaanvoerbronnen.

Geen detectie van etniciteit, nationaliteit of gezongen taal op basis van een
artiestennaam. Alleen gecontroleerde artiest-/trackidentiteiten; onbekende
alternatieve artiesten blijven toegelaten.
"""
import re
import unicodedata

from dark_edge_filter import dark_edge_reject_reason

# v218: de historische bronoeverstijgende blokkades los van Dark Edge bewaren.
# Dark Edge mag onbekende artiesten toelaten zonder andere bronnen te wijzigen.
GLOBAL_LEGACY_BLOCKED_ARTISTS = frozenset({
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

# Alleen duidelijk ongewenste mainstream pop / EDM uit de reeds bestaande
# Dark Edge uitsluitingen. Zwaardere rock/punk uit die lijst is eveneens
# uitgesloten volgens de bestaande muziekvoorkeur.
GLOBAL_EXCLUDED_ARTISTS = GLOBAL_LEGACY_BLOCKED_ARTISTS | frozenset({
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
    # Gebruikerskeuzes voor 35 opnames + 7 artiesten, inclusief Roemeense
    # titelregels, gelden voortaan ZONDER bronuitzondering voor alle stations.
    chosen_reason = dark_edge_reject_reason(artist, title)
    if chosen_reason is not None:
        return chosen_reason
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
