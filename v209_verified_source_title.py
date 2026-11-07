"""v209: one source-confirmed spelling correction, never a version downgrade.

Radio: "For Emily, Wherever I May Find Her (live)"
Official Simon & Garfunkel title: "For Emily, Whenever I May Find Her (Live)"
https://simonandgarfunkel.com/track/for-emily-whenever-i-may-find-her-live/
Spotify catalog: Live 1969, exact song and explicitly LIVE recording.
https://open.spotify.com/album/1agP6sAeWsH8Pgm8WrVtdl
"""


def verified_emily_live_source_title(artist, title):
    if (str(artist or "").strip().casefold() == "simon & garfunkel"
            and str(title or "").strip().casefold()
                == "for emily, wherever i may find her (live)"):
        return "For Emily, Whenever I May Find Her (live)"
    return str(title or "").strip()
