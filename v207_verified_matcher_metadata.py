"""v207: bewezen artiest-/versie-metadata uit twee echte matcher-rapporten.

NOOIT fuzzy identity. Slechts volledige, expliciet gecontroleerde
artiestcredits; titel en versie blijven de normale matcher doorlopen.
Geen Spotify-/netwerkverzoeken en geen automatische requeue.
"""
import re


# The Giraffe Told Me in My Dream explicitly co-labels itself with the Chinese
# band name on its own StreetVoice page, including the song "Before":
# https://streetvoice.com/tgtmimdtheband/
# https://streetvoice.com/tgtmimdtheband/songs/album/97323437/
# Fink (UK): report catalog result is Fink / Looking Too Closely; the country
# qualifier is not part of the Spotify primary artist's name. The same exact
# title is still mandatory in the general matcher.
_EXACT_ARTIST_EQUIVALENTS = {
    "fink (uk)": "Fink",
    "the giraffe told me in my dream": "我夢見長頸鹿對我說",
}


def verified_artist_search_name(artist, title):
    """Only an exact complete source credit has an alternative search form."""
    raw = str(artist or "").strip()
    if raw.casefold() == "fink (uk)" and str(title or "").strip().casefold() == "looking too closely":
        return "Fink"
    if (raw.casefold() == "the giraffe told me in my dream"
            and str(title or "").strip().casefold() == "before"):
        return "我夢見長頸鹿對我說"
    return raw


def verified_artist_identity(source_artist, spotify_primary, source_title, spotify_title):
    """A narrowly source-verified name equivalence, not a substring bypass."""
    raw = str(source_artist or "").strip().casefold()
    candidate = str(spotify_primary or "").strip().casefold()
    requested = str(source_title or "").strip().casefold()
    catalog_title = str(spotify_title or "").strip().casefold()
    expected = _EXACT_ARTIST_EQUIVALENTS.get(raw)
    if not expected or expected.casefold() != candidate:
        return False
    # Only report-verified original track contexts, not every future recording
    # of the same artist with a short or ambiguous title.
    return (raw == "fink (uk)" and requested == "looking too closely"
            and catalog_title == "looking too closely") or (
        raw == "the giraffe told me in my dream" and requested == "before"
        and catalog_title == "before"
    )


def verified_balthazar_castle_version(source_artist, source_title, spotify_artist, spotify_title):
    """Explicitly proved same named recording, NEVER the ordinary studio mix.

    Balthazar's own record label lists 'On A Roll (Sand Castle Tapes version)';
    Spotify catalogs 'On A Roll - Sand Castle Tapes'. Both names specify
    Sand Castle Tapes, unlike 'On A Roll' without this version marker.
    https://balthazar.pias.com/release/300473-balthazar-the-sand-castle-tapes
    https://open.spotify.com/track/6i4YU1gjK2EEZcIMAIDCrA
    """
    return (
        str(source_artist or "").strip().casefold() == "balthazar"
        and str(spotify_artist or "").strip().casefold() == "balthazar"
        and re.fullmatch(
            r"on a roll\s*\(\s*sand castle tapes version\s*\)",
            str(source_title or "").strip(), flags=re.I,
        ) is not None
        and re.fullmatch(
            r"on a roll\s*[-–—]\s*sand castle tapes",
            str(spotify_title or "").strip(), flags=re.I,
        ) is not None
    )
