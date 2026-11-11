"""Conservatieve, door PR te reviewen matcher-zoekhints uit dagrapporten.

Een hint verandert alleen de BESTAANDE derde Spotify-zoekaanvraag.
Nooit de aanvaarding, extra API-verzoeken, een Spotify-ID of de playlist.
De JSON wordt uitsluitend na review/merge actief.
"""
import json
import re
from pathlib import Path

_HINT_FILE = Path(__file__).with_name("v223_matcher_search_hints.json")
_ALLOWED_SOURCES = frozenset({
    "vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled",
    "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge",
    "dkfm_shoegaze", "dkfm_classic", "duyster",
})


def _key(value):
    return " ".join(str(value or "").casefold().split())


def load_hints(path=_HINT_FILE):
    """Ongeldige/misvormde hints stoppen veilig in plaats van gokken."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Ongeldig matcherhint-bestand")
    rows = data.get("hints")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Te veel of ongeldige matcherhints")
    hints = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Ongeldige matcherhint")
        artist, title = row.get("artist"), row.get("title")
        source = row.get("source")
        reports = row.get("independent_reports")
        if (not isinstance(artist, str) or not isinstance(title, str)
                or not artist.strip() or not title.strip()
                or len(artist) > 120 or len(title) > 180
                or re.search(r"[\r\n\"\\]", artist + title)
                or source not in _ALLOWED_SOURCES
                or not isinstance(reports, int) or isinstance(reports, bool)
                or reports < 2):
            raise ValueError("Matcherhint zonder exact gecontroleerd metadata-bewijs")
        key = (_key(artist), _key(title))
        if key in hints:
            raise ValueError("Dubbele matcherhint")
        hints[key] = f'"{artist.strip()}" "{title.strip()}"'
    return hints


HINTS = load_hints()


def report_third_search_hint(artist, title, variant):
    """Alleen zoekvariant 2; downstream blijft de originele song leidend."""
    if variant != 2:
        return None
    return HINTS.get((_key(artist), _key(title)))
