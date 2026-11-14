"""v235: brononafhankelijke zoekhints bij structureel kapotte radiometadata.

Alle functies zijn alleen voor Spotify Search QUERY. De oorspronkelijke
artiest/titel blijven verplicht voor bestaande exacte kandidaat-, versie-,
regio- en duplicatecontroles. Nooit een match goedkeuren in deze module.
"""
import re


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
    if int(variant or 0) >= 1:
        core = incomplete_parenthesis_search_core(title)
        if core and search_artist:
            return f'"{search_artist.replace(chr(34), " ")}" "{core.replace(chr(34), " ")}"'
    return result
