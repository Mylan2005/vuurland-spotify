"""v211: source-confirmed, song-scoped search hints from matcher ZIPs 45 & 46.

A hint influences only the ONE already-budgeted Spotify Search request.
No album/credit hint is ever a match approval. The normal hard artist,
version, market, duplicate, ISRC and ambiguity guards stay mandatory.
"""
from __future__ import annotations

# Source records verified by artist / label / music database. Spotify
# availability is NOT implied. Exact artist + title both mandatory.
# Sources:
# Clover World's End Lane:
# https://www.tagtuner.com/music/albums/Clover/World%27s-End-Lane/album-v2eebd0
# Dean Garcia Doom n Boom:
# https://deangarcia.bandcamp.com/album/doom-n-boom
# Hollow Coves Drifting:
# https://musicbrainz.org/artist/f50e7f7a-7c45-4cd1-b541-c2302a1fda65
# Joan Osborne Just Because I'm a Woman:
# https://www.allmusic.com/song/do-i-ever-cross-your-mind-mt0009328352
# The Mynabirds Lovers Know:
# https://themynabirds.bandcamp.com/track/one-foot
# 93MillionMilesFromTheSun Slowdive EP:
# https://93millionmilesfromthesunofficial.bandcamp.com/album/slowdive-ep
# Josh Rouse Nashville:
# https://joshrouse.bandcamp.com/album/nashville
# Le Boeuf Brothers Remixed (SPECIFIC MIX required):
# https://leboeufbrothers.bandcamp.com/album/remixed
# Stephen Duffy & Lilac Time Keep Going:
# https://www.allmusic.com/album/keep-going-mw0000331460
# Tricky/Gravediggaz release is an EP; first song was credited
# to Tricky ONLY: https://www.allmusic.com/album/the-hell-ep--mw0001014338
# No artist-credit override: the matcher rejects Tricky solo if the
# source explicitly requires Tricky & Gravediggaz.
# Young Man Beyond Was All Around Me:
# https://music.apple.com/us/album/unfair/623380558?i=623380955

# Match on the FULL original source identity, not a generic album title
# rule. These 12 keys were independently corroborated, not Spotify-approved.
_CONFIRMED_ALBUM_HINTS = {
    ("clover", "the things"): "World's End Lane",
    ("dean garcia", "broke it down"): "Doom n Boom",
    ("dean garcia", "all the same"): "Doom n Boom",
    ("hollow coves", "heatwave"): "Drifting",
    ("joan osborne", "do i ever cross your mind"): "Just Because I'm a Woman",
    ("the mynabirds", "one foot"): "Lovers Know",
    ("93millionmilesfromthesun", "slowdive"): "Slowdive EP",
    ("josh rouse", "streetlights"): "Nashville",
    ("le boeuf brothers", "red velvet (yellow then blue remix)"): "Remixed",
    ("stephen duffy & the lilac time", "so far away"): "Keep Going",
    ("tricky & gravediggaz", "hell is round the corner"): "The Hell EP",
    ("young man", "unfair"): "Beyond Was All Around Me",
}


def _key(artist: str, title: str) -> tuple[str, str]:
    return (str(artist or "").strip().casefold(),
            str(title or "").strip().casefold())


def album_hint(artist: str, title: str) -> str | None:
    return _CONFIRMED_ALBUM_HINTS.get(_key(artist, title))


def safer_album_query(artist: str, title: str) -> str | None:
    """Track+album fields focus Spotify's top ten, NOT the candidate check."""
    album = album_hint(artist, title)
    if not album:
        return None
    clean_title = str(title).strip().replace('"', " ")
    clean_album = album.replace('"', " ")
    return f'track:"{clean_title}" album:"{clean_album}"'


def confirmed_guest_credit(artist: str, title: str) -> str:
    """Lucy Ryan (Bobbi Lu) is independently confirmed on Atlas, Eros EP.

    See https://luminousdash.be/reviews/album-reviews/the-christian-club-eros/
    The candidate must independently credit The Christian Club AND Bobbi Lu,
    and must have exactly the same song title as normal. No guest deletion.
    """
    raw = str(artist or "").strip()
    if _key(raw, title) == ("the christian club feat. lucy ryan", "atlas"):
        return "The Christian Club feat. Bobbi Lu"
    return raw


def mint_julep_catalog_search_title(artist: str, title: str) -> str | None:
    """Different 2024 marketing/catalog title for the same Mint Julep single.

    Radio/online video: 'All That We'll Ever Be', Spotify release:
    'All We'll Ever Be'. Exact artist + original FULL title required.
    https://hashbrandnew.com/Artists/Mint%2BJulep
    Spotify playlists list 'All We'll Ever Be' (2024 release):
    https://open.spotify.com/embed/playlist/2CCGkoHrI4EnqkLCNTqKd3
    """
    if _key(artist, title) == ("mint julep", "all that we'll ever be"):
        return "All We'll Ever Be"
    return None


def mint_julep_same_single(artist: str, title: str, spotify_artist: str,
                           spotify_title: str, album: str) -> bool:
    """The only approved title variant: FULL title plus catalog single.

    Never equate arbitrary removed words or other artists. Album must be
    an independently known release naming, not a live/remix variant.
    """
    return bool(
        mint_julep_catalog_search_title(artist, title)
        and str(spotify_artist or "").strip().casefold() == "mint julep"
        and str(spotify_title or "").strip().casefold() == "all we'll ever be"
        and str(album or "").strip().casefold() in {
            "all we'll ever be", "wildfire",
        }
    )

# Only FIRST-search hints for the six cases whose exact Spotify catalog
# recording could not be independently confirmed. Never auto-approve matches.
_OTHER_SEARCHES = {
    ("dead can dance", "eleusis"): 'track:"Eleusis" "Dead Can Dance"',
    ("grizzly bear", "boy from school (hot chip cover)"): 'track:"Boy From School" "Grizzly Bear"',
    ("natalie imbruglia", "leave me alone (portishead mix)"): 'track:"Leave Me Alone" "Natalie Imbruglia" Portishead',
    ("the killers", "mr brightside (live acoustic)"): 'track:"Mr Brightside" "The Killers" acoustic live',
    ("the voxx", "border"): 'track:"Border" "The Voxx"',
    ("torpus & the art directors", "the story's all the same"): 'track:"The story''s all the same" Torpus',
}


def unconfirmed_song_search(artist, title):
    """Search hint ONLY, not evidence of catalog availability."""
    return _OTHER_SEARCHES.get(_key(artist, title))


def special_requested_version_is_safe(artist, title, spotify_title, spotify_album,
                                      spotify_version):
    """No studio substitution for specific live/acoustic or named remix."""
    import re
    requested = _key(artist, title)
    text = " ".join((str(spotify_title or ""), str(spotify_album or ""))).casefold()
    if requested == ("the killers", "mr brightside (live acoustic)"):
        return bool(re.search(r"\blive\b", text)
                    and re.search(r"\bacoustic\b", text)
                    and spotify_version in {"live", "acoustic"})
    if requested == ("natalie imbruglia", "leave me alone (portishead mix)"):
        return bool(re.search(r"\bportishead\b", text)
                    and re.search(r"\b(?:mix|remix)\b", text)
                    and spotify_version in {"mix", "remix"})
    return True
