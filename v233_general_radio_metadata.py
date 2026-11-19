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
    # only when followed by a word; standalone decimal titles stay unchanged.
    raw = re.sub(
        r"(?<!\d)([1-9]\d{0,2})[.,](\d{3})(?=\s+[A-Za-z])",
        lambda m: m.group(1) + m.group(2), raw,
    )
    return raw


def normalize_radio_trailing_guest(artist, title):
    """Turn unmistakable radio *guest notation* into a required credit.

    This is NOT song matching. The ordinary candidate matcher still checks
    the main artist, all guests, full title, recording edition and market.
    Any named mix/remix must remain present for edition validation.
    """
    raw = str(title or "").strip()
    artist_raw = str(artist or "").strip()
    if not artist_raw:
        return artist, raw

    # A radio suffix '(Album)' is editorial when used AFTER a feat. marker;
    # keep real 'Album Version' editions intact.
    if re.search(r"(?i)\\s+(?:feat\\.?|ft\\.?|featuring)\\s+", raw):
        raw = re.sub(r"(?i)\\s*\\(album\\)\\s*$", "", raw).strip()

    # Explicit parenthesized radio credit: '(f Lorde)' or '(feat. Q-Tip)'.
    # The full guest identity is mandatory. Never treat arbitrary parenthesis
    # (such as '(Live)' or '(Radio Edit)') as artist metadata.
    m = re.fullmatch(
        r"(.+?)\\s+\\(\\s*(?:f|ft\\.?|feat\\.?|featuring)\\s+([^()]{2,100})\\s*\\)",
        raw, flags=re.I,
    )
    if m:
        core, guest = m.groups()
        guest = guest.strip()
        if re.search(r"[\\w]", guest) and not re.search(r"\\s[-–—]\\s", guest):
            return artist_raw + " feat. " + guest, core.strip()

    # Unparenthesized trailing guests, optionally followed by a NAMED remix.
    m = re.fullmatch(
        r"(.+?)\\s+(?:feat\\.?|ft\\.?|featuring)\\s+"
        r"([^()]{3,90}?)(\\s*\\([^()]*\\bremix\\))?\\s*",
        raw, flags=re.I,
    )
    if not m:
        return artist, raw
    core, guest, remix = m.groups()
    guest = guest.strip()
    if not core.strip() or not re.search(r"\\w", guest) or re.search(r"\\s[-–—]\\s", guest):
        return artist, raw
    return (artist_raw + " feat. " + guest,
            core.strip() + ((" " + remix.strip()) if remix else ""))


def normalize_radio_artist_context(artist):
    """Remove known broadcaster country labels, not arbitrary artist suffixes."""
    raw = str(artist or "").strip()
    return re.sub(r"\\s+\\(\\s*(?:UK|USA)\\s*\\)$", "", raw, flags=re.I)



def normalize_radio_metadata(artist, title):
    """Algemene, bewijsgestuurde metadata-opkuis (nooit fuzzy artiestmatching)."""
    artist_str = str(artist or "").strip()
    corrected_artist = normalize_radio_artist_context(artist)
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
