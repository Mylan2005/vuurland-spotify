"""v215: alle expliciete uitvoeringskenmerken tegelijk vergelijken.

De hoofdmatcher controleert al de titel/hoofdartiest/versiefamilie, maar
version_family() kiest bewust maar één dominante familie. Daardoor kan een
Live Acoustic Remix de 'live'-toets halen voor een gewone live-aanvraag.
Dit is een extra afwijscontrole, nooit een shortcut naar goedkeuring.
Geen netwerk, geen Spotify-zoekaanvragen, geen opgeslagen state.
"""
import re


_HARD_MODIFIERS = (
    ("live", r"\blive\b"),
    ("acoustic", r"\bacoustic\b"),
    ("remix", r"\bremix(?:ed)?\b"),
    ("mix", r"\bmix\b"),
    ("demo", r"\bdemo\b"),
    ("instrumental", r"\binstrumental\b"),
    ("unplugged", r"\bunplugged\b"),
    ("stripped", r"\bstripped\b"),
    ("session", r"\bsession\b"),
    ("karaoke", r"\bkaraoke\b"),
    ("re_recorded", r"\bre[- ]?record(?:ed|ing)?\b|\btaylor[\u2019']?s\s+version\b"),
    ("sped_up", r"\bsped\s+up\b"),
    ("slowed", r"\bslowed\b"),
    ("nightcore", r"\bnightcore\b"),
    ("alternate", r"\balternate\b|\balternative\s+version\b"),
    ("edit", r"\bradio\s+edit\b"),
)


def _explicit_modifiers(title):
    """Scan alleen expliciet afgescheiden labels, niet gewone songtekst.

    'Live Through This' is dus geen live-opname; '(Live at the BBC)'
    is dat wel. Herken meerdere labels uit één suffix tegelijk.
    """
    raw = str(title or "").casefold().replace("–", "-").replace("—", "-")
    segments = re.findall(r"\(([^()]*)\)|\[([^\[\]]*)\]", raw)
    pieces = [left or right for left, right in segments]
    pieces.extend(re.split(r"\s+-\s+", raw)[1:])
    suffix = " | ".join(pieces)
    detected = {
        name for name, regex in _HARD_MODIFIERS
        if re.search(regex, suffix)
    }
    # Remix bevat niet het losse woord 'mix', maar bijvoorbeeld
    # 'Acoustic Mix' en 'Acoustic Remix' zijn wel verschillende versies.
    return frozenset(detected)


def has_unrequested_performance_modifiers(requested_title, candidate_title):
    """Weiger bijkomende ongewenste opnamekenmerken.

    Alleen als de bron zelf expliciet een uitvoeringsversie vraagt.
    Bij gewone liedtitels blijven de bestaande globale versie/fallback-
    regels leidend (compatibel met bestaande releases).
    """
    requested = _explicit_modifiers(requested_title)
    if not requested:
        return False
    candidate = _explicit_modifiers(candidate_title)
    return bool(candidate - requested)
