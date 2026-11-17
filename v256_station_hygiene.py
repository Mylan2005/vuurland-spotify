"""v256: station-only announcements and bounded hard-rock cautions.

Do not infer metal from unknown artists, nor ban all of Muse, Biffy Clyro
or Royal Blood. Existing global exclusions handle known metal/nu-metal.
No Spotify requests are ever used for the station-specific filtering.
"""
import re


def non_music_fragment(source, artist, title):
    a = str(artist or "").strip().casefold()
    t = str(title or "").strip().casefold()
    if not a or not t:
        return True
    if source == "radio_britannia":
        return a in {"daniel roggiano", "radio britannia"} and bool(re.search(
            r"\b(?:britannia|separador|apertura|estas escuchando|estás escuchando)\b", t
        )) or a == "daniel roggiano"
    if source != "wbru":
        return False
    # Station IDs in seven source playlists arrive as 'artist - spoken text'.
    # Require clear broadcasting vocabulary, never a generic word 'radio',
    # 'new music', 'live' or a particular musical artist.
    broadcast = re.search(
        r"\b(?:wbru|whiskey bravo romeo uniform|dj\s+|"
        r"you're listening to|you.re listening to|"
        r"this is (?:the|your)?\s*wbru|"
        r"here.s new music (?:from|on) wbru|"
        r"best of indie and alternative|"
        r"new music on wbru|"
        r"wbru suggestion box|"
        r"retro lunch)\b", t
    )
    announcer = (
        a.startswith("dj ") or a.startswith("djs ") or a.startswith("dj,")
        or a in {"a&p", "blue", "gabriella", "carolyn fox", "rex and carolyn fox",
                 "seth", "tv", "news", "movies", "technology"}
        or "ben cunningham" in a or "sean fay wolfe" in a
        or "luci" in a and "jones" in a
    )
    return bool(broadcast) and (announcer or "wbru" in t)


def britannia_heavy_caution(artist, title):
    """Skip only exact extreme/punk-metal performances, not all guitar rock.

    The global music policy is the authority for blocked heavy artists;
    this hook does not guess from artist similarity or genres.
    """
    # No blanket bans on Muse's Stockholm Syndrome, Royal Blood or Biffy:
    # the user wants more Muse and likes some heavier alternative rock.
    return False
