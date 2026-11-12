"""v232: uitsluitend extern bevestigde RadioBox metadata-correcties.

Deze functie verandert alleen lokale matchervariabelen. Geen nieuwe Spotify
Search, URI-autorisatie, FIFO-mutatie of automatische playlisttoevoeging.
"""


def verified_radio_metadata(artist, title):
    key = (str(artist or "").casefold().strip(),
           str(title or "").casefold().strip())
    # DKFM Shoegaze schrijft in het titelveld nog eens de artiest.
    # VAR - Run staat op The Never-Ending Year (Spartan Records, 2020).
    if key == ("var", "var - run"):
        return artist, "Run"
    # Originele Cranes-release Loved (Dedicated, 1994) noemt het Rêverie.
    # RadioBox heeft een Cyrillische к i.p.v. de letter ê overgenomen.
    if key == ("cranes", "rкverie"):
        return artist, "Rêverie"
    return artist, title
