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



def normalize_radio_filename_and_number(title):
    """Remove *unambiguous* broadcast filename tags; preserve song identity.

    Only a track number plus bit depth plus trailing date identifies a file
    export. Ordinary numbers, dates and explicit song editions remain intact.
    """
    raw = str(title or "")
    tagged = re.fullmatch(
        r"\s*\d{1,2}\s+(.+?)\s+(?:16|24|32)bit\s+"
        r"\d{1,2}[._-]\d{1,2}[._-]\d{2,4}\s*",
        raw, flags=re.IGNORECASE,
    )
    if tagged:
        raw = tagged.group(1).strip()
        # English contraction from the file's de-punctuated name.
        raw = re.sub(r"(?i)^im\b", "I'm", raw)
    # 1.000 Times / 1,000 Times are the same integer, never a decimal
    # because precisely three digits are required after the separator.
    raw = re.sub(
        r"(?<!\d)([1-9]\d{0,2})[.,](\d{3})(?!\d)",
        lambda m: m.group(1) + m.group(2), raw,
    )
    return raw


def normalize_radio_trailing_guest(artist, title):
    """Move an explicit *trailing* radio guest into the required artist credit.

    Spotify still has to verify ALL credited performers and the entire song
    title/edition. In particular, a named remix is never stripped.
    """
    raw = str(title or "").strip()
    # Radio station notation '(Album)' is not a named mix/edit and appears
    # after an explicit guest in syndicated station metadata.
    album_suffix = re.search(r"(?i)\s*\(album\)\s*$", raw)
    if album_suffix and re.search(r"(?i)\s+(?:feat\.?|ft\.?|featuring)\s+",
                                  raw[:album_suffix.start()]):
        raw = raw[:album_suffix.start()].rstrip()

    # Optional NAMED remix is retained as a required recording edition.
    match = re.fullmatch(
        r"(.+?)\s+(?:feat\.?|ft\.?|featuring)\s+"
        r"([^()]{3,90}?)(\s*\([^()]*\bremix\))?\s*",
        raw, flags=re.IGNORECASE,
    )
    if not match:
        return artist, raw
    core, guest, remix = match.groups()
    guest = guest.strip()
    # Avoid treating separators or malformed station noise as a performer.
    if not core.strip() or not re.search(r"\w", guest) or re.search(r"\s[-–—]\s", guest):
        return artist, raw
    artist_raw = str(artist or "").strip()
    if not artist_raw:
        return artist, raw
    # The featured name remains mandatory for Spotify candidate validation.
    updated_artist = artist_raw + " feat. " + guest
    updated_title = core.strip() + ((" " + remix.strip()) if remix else "")
    return updated_artist, updated_title

def normalize_radio_metadata(artist, title):
    """Algemene, bewijsgestuurde metadata-opkuis (nooit fuzzy artiestmatching)."""
    artist_str = str(artist or "").strip()
    corrected_artist = artist
    # In een expliciete radiocredit 'A x B' is x een samenwerkingsscheiding,
    # geen deel van de artiestennaam. Deze vormcorrectie mag alleen met twee
    # volledige, niet-lege namen; de matcher verifieert nog beide credits.
    radio_duo = re.fullmatch(r"(.{2,}?)\s+x\s+(.{2,}?)", artist_str)
    if radio_duo:
        corrected_artist = f"{radio_duo.group(1).strip()} & {radio_duo.group(2).strip()}"
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
    title_str = normalize_radio_filename_and_number(title_str)
    corrected_artist, title_str = normalize_radio_trailing_guest(corrected_artist, title_str)
    return corrected_artist, title_str
