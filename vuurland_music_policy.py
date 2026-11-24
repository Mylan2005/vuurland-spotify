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
    # Persoonlijke uitsluiting: Lambrini Girls uit alle bronnen weren.
    "lambrini girls",
    # Further explicit extreme-metal and hardcore exclusions.
    "insomnium", "amon amarth", "arch enemy", "children of bodom", "kalmah",
    "wintersun", "hypocrisy", "kataklysm", "vader", "krisiun",
    "incantation", "autopsy", "immolation", "grave", "dismember",
    "entombed", "unleashed", "bolt thrower", "asphyx", "benediction",
    "origin", "beneath the massacre", "archspire", "necrophagist", "spawn of possession",
    "the faceless", "rings of saturn", "infant annihilator", "vulvodynia", "angelmaker",
    "shadow of intent", "brand of sacrifice", "signs of the swarm", "to the grave", "abominable putridity",
    "celtic frost", "hellhammer", "bathory", "venom", "deströyer 666",
    "tsjuder", "carpathian forest", "taake", "horna", "rotting christ",
    "anaal nathrakh", "blut aus nord", "mgła", "inquisition", "pro-pain",
    "biohazard", "walls of jericho", "first blood", "born from pain", "sworn enemy",
    "blood for blood", "wisdom in chains", "death before dishonor", "no turning back", "backtrack",
    "trapped under ice", "incendiary", "jesus piece", "kublai khan tx", "vein.fm",
    "code orange", "nails", "full of hell", "pig destroyer", "darkest hour",
    "hatesphere", "prong", "xentrix", "cirith ungol", "yngwie malmsteen",
    "seventh wonder", "broken by the scream", "ram", "diggeth", "forbidden",
    "bombus", "flotsam and jetsam", "annihilator", "death angel", "tankard",
    "whiplash", "razor", "onslaught", "violator",
    # Explicit user exclusions: punk, hardcore and abrasive alternative.
    "black flag", "circle jerks", "suicidal tendencies", "bad brains",
    "turnstile", "ministry", "amyl and the sniffers",
    "sprints", "starcrawler", "a place to bury strangers",
    # Clearly established hardcore punk, extreme metal and metalcore acts.
    "minor threat", "dead kennedys", "agnostic front", "madball",
    "cro-mags", "discharge", "the exploited", "gbh", "negative approach",
    "germs", "fear", "poison idea", "the casualties", "sick of it all",
    "hatebreed", "converge", "terror", "knocked loose", "earth crisis",
    "napalm death", "cannibal corpse", "slayer", "death", "obituary",
    "deicide", "morbid angel", "carcass", "mayhem", "darkthrone",
    "immortal", "emperor", "behemoth", "meshuggah", "lamb of god",
    "whitechapel", "suicide silence", "lorna shore", "thy art is murder",
    "parkway drive", "killswitch engage", "as i lay dying",
    "bullet for my valentine", "asking alexandria", "motionless in white",
    # Additional explicit heavy music exclusions, exact artist identities only.
    "anthrax", "testament", "exodus", "overkill", "kreator", "sodom", "destruction", "sepultura", "sacred reich", "nuclear assault", "municipal waste", "havok", "warbringer", "voivod",
    "iron maiden", "judas priest", "manowar", "accept", "saxon", "hammerfall", "blind guardian", "dragonforce", "sabaton", "powerwolf", "helloween", "running wild", "gloryhammer", "beast in black", "iron savior",
    "cryptopsy", "dying fetus", "suffocation", "nile", "decapitated", "aborted", "bloodbath", "benighted", "cattle decapitation", "belphegor", "marduk", "gorgoroth", "1349", "watain", "satyricon", "dark funeral",
    "the ghost inside", "august burns red", "miss may i", "unearthed", "all that remains", "bleeding through", "bury tomorrow", "fit for an autopsy", "chelsea grin", "oceano", "despised icon", "carnifex", "spite", "enterprise earth",
    "strife", "snapcase", "comeback kid", "bane", "have heart", "gallows", "the bronx", "the varukers", "chaos uk", "anti cimex", "disfear", "tragedy", "doom", "extreme noise terror", "subhumans",
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
