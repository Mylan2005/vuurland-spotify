"""v216: exact afgebakende metadata-correcties uit matcher-rapport 2026-11-09.

Alleen schrijfwijze van een volledige bekende artiest/titel of expliciete
credits. Dit zijn GEEN bewezen Spotify-URI's en GEEN automatische approvals:
de volledige Spotify-artiest-, titel-, versie-, markt- en ISRC-veiligheid
blijft onverkort vereist. Onbekende kandidaten worden niet gegokt.
"""
import re


def report_metadata_correction(artist, title):
    """Geef (zoek-/match-artiest, zoek-/match-titel) voor exacte rapportparen."""
    original_artist = str(artist or "").strip()
    original_title = str(title or "").strip()
    key = (re.sub(r"\s+", " ", original_artist).casefold(),
           re.sub(r"\s+", " ", original_title).casefold())

    corrections = {
        # Kandidaten met dezelfde opname-identiteit in de aangeleverde log.
        ("!!! (chk chk chk)", "am/fm"): ("!!!", "AM/FM"),
        ("cole, lloyd", "backwoods ( reprise )"): ("Lloyd Cole", "Backwoods (Reprise)"),
        ("hayien", "hayien - somehow i still manage"):
            ("Hayien", "Somehow I Still Manage"),
        # Exacte tijdnotatie van het benoemde nummer behouden; uitsluitend
        # scheiding na dubbele punt gelijkzetten aan kandidaatmetadata.
        ("oeil", "quiet lights (2:00 am version)"):
            ("Oeil", "Quiet Lights (2: 00 AM Version)"),
        # Geen algemene Romeins-cijfervergelijking: i/1 alleen voor dit lied.
        ("slowdive", "avalyn 1"): ("Slowdive", "Avalyn I"),
        # Bewaar alle gecrediteerde gasten; andere volgorde in Spotify mag
        # door de bestaande volledige artiestencontrole worden beoordeeld.
        ("glen hansard featuring eddie vedder & jake clemons", "drive all night"):
            ("Glen Hansard feat. Eddie Vedder feat. Jake Clemons", "Drive All Night"),
        ("tucker zimmerman feat big thief, twain & iji", "burial at sea"):
            ("Tucker Zimmerman feat. Big Thief feat. Twain feat. Iji", "Burial at sea"),
    }
    return corrections.get(key, (original_artist, original_title))


def has_report_correction(artist, title):
    original = (str(artist or "").strip(), str(title or "").strip())
    return report_metadata_correction(artist, title) != original
