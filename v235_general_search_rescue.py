"""v235: brononafhankelijke zoekhints bij structureel kapotte radiometadata.

Alle functies zijn alleen voor Spotify Search QUERY. De oorspronkelijke
artiest/titel blijven verplicht voor bestaande exacte kandidaat-, versie-,
regio- en duplicatecontroles. Nooit een match goedkeuren in deze module.
"""
import re

from v239_structural_title_rescue import safe_search_title
from v241_final_plural_rescue import final_s_candidate_title


def catalog_search_artist(artist):
    """'T R A C E S' -> 'TRACES' als ALLE tokens losse letters zijn.

    Alleen bij 4-14 losse Latin letters: bandnamen, initialen en gemengde
    artiestcredits mogen niet automatisch worden veranderd.
    """
    text = str(artist or "").strip()
    if re.fullmatch(r"[A-Za-z](?:\s+[A-Za-z]){3,13}", text):
        return "".join(text.split())
    return artist


def incomplete_parenthesis_search_core(title):
    """Zoekkern voor afgekapt '(remix ...', '(radio ...', '(Beyonce...'.

    Een open haakje aan het eind is onbetrouwbare radiometadata. De zoekterm
    wordt breder, maar de echte candidate-versie mag NOOIT via deze functie
    als gelijk aan de oorspronkelijke remix/live worden beoordeeld.
    """
    raw = str(title or "").strip()
    if not raw or raw.count("(") <= raw.count(")"):
        return None
    position = raw.find("(")
    if position <= 0:
        return None
    core = raw[:position].strip(" -–—")
    # Geen halve titel als kern: min. twee titelwoorden en geen eind-"feat".
    if len(core) < 7 or len(core.split()) < 2:
        return None
    if re.search(r"(?i)\b(?:feat|ft|featuring|with|and|the|of)\.?$", core):
        return None
    return core


def split_compound_light_title(title):
    """'Streetlights' -> 'Street Lights' als alternatieve ZOEKterm.

    Het betreft een generieke, strikt structurele woordgrens bij enkelvoudige
    titels, geen catalogusgoedkeuring; de bestaande title_identity moet daarna
    beide volledige titels als dezelfde letterreeks bewijzen.
    """
    raw = str(title or "").strip()
    m = re.fullmatch(r"([A-Za-z]{4,})(lights?)", raw, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1) + " " + m.group(2)


def alternate_remix_credit_search(title):
    """Only alter query syntax: '(Remix by X)' -> '(X Remix)'.

    Never remove the required remixer/recording version; candidates still pass
    the original artist, title, version and territory gates.
    """
    raw = str(title or "").strip()
    match = re.search(r"\\(remix by ([^()]{2,70})\\)$", raw, flags=re.I)
    if not match:
        return None
    remixer = match.group(1).strip()
    if re.search(r"(?i)\\b(?:feat|ft|with)\\b", remixer):
        return None
    return raw[:match.start()] + f"({remixer} Remix)"


def rescue_search_query(artist, title, query, variant):
    """Herschrijf hoogstens de reeds geplande Search; geen extra HTTP-call.

    Ongeldige versieaanduidingen worden uitsluitend op een volgende
    bestaande zoekbeurt verbreed, zodat poging 0 intact blijft.
    """
    original_artist = str(artist or "").strip()
    search_artist = str(catalog_search_artist(original_artist) or "").strip()
    result = str(query or "").strip()
    if search_artist != original_artist and original_artist:
        # De originele query hoeft niet opnieuw samengesteld te worden:
        # vervang uitsluitend letter-voor-letter tokens als HELE woordgroep.
        result = result.replace(original_artist, search_artist)
    # v241: on an existing retry only, query final-s plural title forms;
    # search alone never authorizes a track or removes guest/version checks.
    _v241_plural = final_s_candidate_title(title) if int(variant or 0) >= 1 else None
    if _v241_plural and search_artist:
        return f'"{search_artist.replace(chr(34), " ")}" "{_v241_plural.replace(chr(34), " ")}"'
    # Source-independent title variants on the already budgeted retry call.
    # Never change the version or trust a search query as a match decision.
    _v239_title = safe_search_title(original_artist, title, variant)
    if _v239_title and search_artist:
        return f'"{search_artist.replace(chr(34), " ")}" "{_v239_title.replace(chr(34), " ")}"'
    if int(variant or 0) >= 1:
        remix_alternative = alternate_remix_credit_search(title)
        if remix_alternative and search_artist:
            return f'"{search_artist.replace(chr(34), " ")}" "{remix_alternative.replace(chr(34), " ")}"'
    if int(variant or 0) == 1:
        split_lights = split_compound_light_title(title)
        if split_lights and search_artist:
            return f'"{search_artist.replace(chr(34), " ")}" "{split_lights}"'
    if int(variant or 0) >= 1:
        core = incomplete_parenthesis_search_core(title)
        if core and search_artist:
            return f'"{search_artist.replace(chr(34), " ")}" "{core.replace(chr(34), " ")}"'
    return result
