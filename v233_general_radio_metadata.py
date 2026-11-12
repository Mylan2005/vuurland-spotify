"""v233: strikt structurele, generieke RadioBox-metadatacorrecties.

Alleen dezelfde volledige artiestnaam, direct gevolgd door een expliciete
titel-separator, mag uit de titelprefix worden verwijderd. Bij gemengde
Latijns/Cyrillische woorden worden enkel duidelijk visueel identieke tekens
hersteld; volledig Cyrillische woorden en niet-confusable letters blijven staan.
Spotify valideert na correctie nog steeds dezelfde titel, artiest, versie,
regio en duplicaten. De oorspronkelijke bronkeys blijven onveranderd.
"""
import re
import unicodedata


# Alleen tekens die er in Latijnse woorden exact als deze letters uitzien.
# 'к' is bewust NIET opgenomen: Rкverie -> Rêverie is géén
# algemene Unicode-regel maar blijft een afzonderlijk bevestigde correctie.
_CYRILLIC_LOOKALIKES = str.maketrans({
    "а": "a", "А": "A",
    "е": "e", "Е": "E",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "с": "c", "С": "C",
    "х": "x", "Х": "X",
    "у": "y", "У": "Y",
    "і": "i", "І": "I",
    "ј": "j", "Ј": "J",
    "ѕ": "s", "Ѕ": "S",
    "ѵ": "v", "Ѵ": "V",
    "ԁ": "d", "Ԁ": "D",
    "һ": "h", "Һ": "H",
})


def _normalize_mixed_script_word(word):
    has_latin = any("LATIN" in unicodedata.name(c, "") and c.isalpha()
                    for c in word)
    has_cyrillic = any("CYRILLIC" in unicodedata.name(c, "") and c.isalpha()
                       for c in word)
    if not (has_latin and has_cyrillic):
        return word
    # Indien een onbekende Cyrillische letter voorkomt, GEEN gedeeltelijke
    # correctie: die kan een betekenisvol ander woord betekenen.
    if any("CYRILLIC" in unicodedata.name(c, "") and c.isalpha()
           and ord(c) not in _CYRILLIC_LOOKALIKES for c in word):
        return word
    return word.translate(_CYRILLIC_LOOKALIKES)


def normalize_mixed_script_typos(title):
    """Corrigeer alleen gemengde scripts met volledig bekende lookalikes."""
    text = unicodedata.normalize("NFC", str(title or ""))
    return re.sub(r"[^\W\d_]+", lambda m: _normalize_mixed_script_word(m.group(0)),
                  text, flags=re.UNICODE)


def normalize_radio_metadata(artist, title):
    """Algemene, bewijsgestuurde metadata-opkuis (nooit fuzzy artiestmatching)."""
    artist_str = str(artist or "").strip()
    title_str = str(title or "")  # originele spaties bewaren als er geen correctie is
    # De artiest moet in zijn VOLLEDIGE vorm vooraan staan, niet als
    # gedeeltelijke bandnaam of gewoon eerste woord van een echte titel.
    # Vereis een ondubbelzinnige ' - ' / ' — ' separator (met spaties).
    match = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", title_str)
    if match and artist_str:
        prefix = " ".join(match.group(1).casefold().split())
        wanted = " ".join(artist_str.casefold().split())
        if prefix == wanted and match.group(2).strip():
            title_str = match.group(2).strip()
    title_str = normalize_mixed_script_typos(title_str)
    return artist, title_str
