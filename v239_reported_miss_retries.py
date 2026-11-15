"""One-time replay eligibility for an explicitly supplied failed-match report.

These are *source observations*, not verified Spotify tracks. The v203 requeue
engine requires original failed-cache evidence, a valid original station,
eligibility, FIFO capacity and a normal Spotify match before anything adds.
The malformed Morse-like Duyster line is deliberately not included.
"""
_REPORTED = frozenset({
    ("Josh Rouse", "Streetlights"),
    ("Indoor Voices", "Care Too Much"),
    ("The Tallest Man On Earth", "Where Do My Bluebirds Fly"),
    ("ÉTIENNE DE CRÉCY WITH ALEX GOPHER", "Smile"),
    ("Lilac", "Sun"),
    ("Le Boeuf Brothers", "Red Velvet (Yellow Then Blue Remix)"),
    ("zlap.", "sunlight"),
    ("Haruko", "Man In The Moon"),
    ("Maria Taylor", "Two of Those Too"),
    ("On And On", "Ghosts"),
    ("Smashing Pumpkins", "Tom Tom"),
    ("Hotline TNT", "Spot Me 100"),
    ("Seekae", "3 (Three)"),
    ("Rochus Grolle & Michael Noack feat. Alex Landon", "Why"),
    ("Blush", "Blush-Lover-s-Speed"),
    ("GoldLink x Hare Squead", "Herside Story"),
    ("Florence And The Machine", "Flakes (Mystery Jets cover)"),
    ("Ollie Brown", "Midnight Call"),
    ("Kyle Dixon & Michael Stein", "Stranger Things Theme (Extended)"),
    ("Olympic Swimmers", "Apples and Pears"),
    ("Fenech-Soler", "Lies (Original)"),
    ("Arcana Arcade", "Clock Said All Aboard"),
    ("Torpus & the Art Directors", "The story's all the same"),
    ("Grizzly Bear", "Boy From School (Hot Chip Cover)"),
    ("Erik Blood", "Share Your Love"),
    ("Gallant feat. Sufjan Stevens & Rebecca Sugar", "Toogoodtobetrue"),
})

def _norm(value):
    return " ".join(str(value or "").casefold().split())

_REPORTED_KEYS = frozenset((_norm(artist), _norm(title))
                           for artist, title in _REPORTED)

def reported_for_safe_retry(artist, title):
    return (_norm(artist), _norm(title)) in _REPORTED_KEYS
