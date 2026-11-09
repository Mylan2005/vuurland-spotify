"""v217: onafhankelijke derde zoekroute voor echte missers uit rapport #48.

Dit wijzigt ALLEEN de bestaande zoekquery tijdens poging 2, nooit het
aantal Spotify-calls, de bron-identiteit, de kandidaatvalidatie of het
gewenste opname-type. De rapportage bewijst geen beschikbaarheid.
"""
import re


# Geen onbetrouwbare Spotify IDs of aangenomen artiestaliases:
# deze bronparen hebben in run #48 geen betrouwbare match opgeleverd.
_REPORTED = {
    ("comsat angels", "shiva descending"):
        ('"Comsat Angels" "Shiva Descending"'),
    ("eyelash", "strawberry"):
        ('"eyelash" "Strawberry"'),
    ("fragile animals", "breathe out and in"):
        ('"Fragile Animals" "Breathe Out And In"'),
    ("hatchie", "eyes without a face"):
        ('"Hatchie" "Eyes Without A Face"'),
    ("loom", "slowmotion"):
        ('"Loom" "Slowmotion"'),
    ("more earth than sea", "alone again"):
        ('"More Earth Than Sea" "Alone Again"'),
    ("phosphene", "black sheep"):
        ('"Phosphene" "Black Sheep"'),
    ("shout out louds", "hard rain (live from haldern festival)"):
        ('"Shout Out Louds" "Hard Rain" "Haldern"'),
    ("tombstones in their eyes", "fall"):
        ('"Tombstones In Their Eyes" "Fall"'),
    ("ultra vivid scene", 'mercy seat (12")'):
        ('"Ultra Vivid Scene" "Mercy Seat"'),
    ("virgins", "s o f t e r"):
        ('"Virgins" "softer"'),
}


def report_third_search_query(artist, title, variant):
    """Exacte bronsong, uitsluitend derde zoekpoging.

    De bestaande matcher controleert altijd de ONGEWIJZIGDE titel, alle
    volledige artiestcredits en eventuele benoemde live/remix-versies.
    """
    if variant != 2:
        return None
    key = (re.sub(r"\s+", " ", str(artist or "").strip()).casefold(),
           re.sub(r"\s+", " ", str(title or "").strip()).casefold())
    return _REPORTED.get(key)


def has_report_search_rescue(artist, title):
    return report_third_search_query(artist, title, 2) is not None
