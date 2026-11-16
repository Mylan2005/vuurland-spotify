"""v242: user-observed Spotify misses from 16 Nov 2026, NOT verified recordings.

Each record names the observed radio source; a replay is allowed ONLY when
an original persisted failure with that exact source exists. No Spotify ID,
metadata rewrite, or match approval is provided by this table.
"""

REPORTED_MISSES = (
    ("dj_neihtul", "Sabres of paradise", "Wilmot (Remix by Red snapper)"),
    ("gri_balkon", "David August", "Ingrid"),
    ("indie_select", "A Certain Ratio", "Bootsy (Swingfire Mix)"),
    ("egofm_rnb", "Q", "Take Me Where Your Heart Is"),
    ("gri_balkon", "Youandewan", "93"),
    ("radio_x_chilled", "Brooke Combe", "Broken Stones (Live at On The Beach)"),
    ("indie_select", "The Kissaway Trail", "Telly The Truth (The Breach)"),
    ("dkfm_edge", "plant cell", "Speed Games at Daytona Beach"),
    ("dj_neihtul", "Ronny Jordan meets DJ Krush", "Love I never had so good"),
    ("indie_select", "Dirk Darmstädter", "everything beautiful"),
    ("gri_balkon", "Jetlag, Esther", "Walk With Me"),
    ("indie_select", "Two Door Cinema Club", "Undercover Martyn Flexin' It (Passion Pit Remix)"),
    ("indie_select", "Comsat Angels", "Our Secret"),
    ("dark_edge", "THEOPHILUS LONDON, TAME IMPALA", "Whiplash (feat. Tame Impala)"),
    ("dkfm_shoegaze", "Spotlight Kid", "With Every Heartbeat"),
    ("big_sonic_heaven", "Intermix", "Voices"),
    ("dreampop_radio", "Liam Finn Eliza Jane", "Plane Crash"),
    ("egofm_rnb", "Lion Babe", "Wonder Woman (Suff Daddy Remix)"),
    ("dreampop_radio", "The La's", "There She Goes Again"),
    ("gri_balkon", "Seb Wildblood", "The One with the Emoticon"),
    ("big_sonic_heaven", "My Bloody Valentine", "We Have All the Time In the World"),
    ("dreampop_radio", "Eva & Manu", "Empty"),
    ("dj_neihtul", "Aitor Escobar", "Mi Keni"),
    ("big_sonic_heaven", "Fleeting Joys", "Hooked Into My Soul"),
    ("indie_select", "Wire", "B/W Silence"),
    ("egofm_rnb", "Terrace Martin, Robert Glasper, 9th Wonder & Kamasi Washington feat. Phoelix", "Freeze Tag"),
    ("egofm_chillout", "Feist", "Bittersweet Melodies (Christian Strobe Remix)"),
    ("dj_neihtul", "Arnica Montana", "Sweet Scented South"),
    ("duyster", "L'Usine", "Contamination"),
    ("big_sonic_heaven", "The Churchhill Garden & Andy Jossi", "Noise (feat. Krissy Vanderwoude)"),
    ("indie_select", "Alias", "Autumnal Ego"),
    ("egofm_chillout", "ASTA", "My Heart is on Fire (Marius Hörsturz Edit)"),
    ("dj_neihtul", "The Birdstones", "Closer"),
    ("gri_balkon", "Pale", "Fearing Faces (Vondelpark Dub Mix)"),
    ("indie_select", "Freebass", "The Only Ones Alone"),
    ("dreampop_radio", "Yo La Tengo", "I'm On My Way"),
    ("dkfm_classic", "Eugenius", "Hot Dog"),
    ("duyster", "Thalia Zedek", "Excommunications (Everybody Knows)"),
    ("egofm_chillout", "Art of Noise", "Moments In Love (7 inch version)"),
    ("dkfm_shoegaze", "Tristesse Club", "Mind"),
    ("gri_balkon", "Räubermukke", "Vogelfutter (Le Vold Remix)"),
    ("ignoreradio_shoegaze", "Film School", "Bright to Death"),
    ("duyster", "Mogwai", "Star Wars"),
    ("big_sonic_heaven", "SPC ECO", "Nobody Knows"),
    ("dkfm_edge", "Lesser Angels", "Burn It Away"),
    ("dj_neihtul", "James Bright & Pete Gooding", "Chilli Squid"),
    ("dkfm_shoegaze", "Spotlight Kid", "NVMBR"),
    ("ignoreradio_shoegaze", "Zwan", "Honestly"),
    ("duyster", "Llips", "The Brooklyn Attitude"),
    ("big_sonic_heaven", "Stefano Guzzetti", "La Ment (w/ Ayu Okakita)"),
    ("dj_neihtul", "Digital Analog Band", "Waiting 4 You"),
)


def _norm(value):
    return " ".join(str(value or "").casefold().split())

_KEYS = frozenset((_norm(artist), _norm(title), source)
                  for source, artist, title in REPORTED_MISSES)


def reported_v242_for_safe_retry(artist, title, source):
    return (_norm(artist), _norm(title), source) in _KEYS


def reported_v242_track(artist, title):
    return any(_norm(artist) == a and _norm(title) == t
               for a, t, _source in _KEYS)
