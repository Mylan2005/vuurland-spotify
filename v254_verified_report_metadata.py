"""v254: exact report metadata corrections with independent catalog evidence.

No Spotify IDs or blind approvals: all results must pass the existing strict
artist, title, guest-credit, version, market, and deduplication checks.
The source key and queue item must remain unchanged.
"""
import re


def report_correction(artist, title):
    a = str(artist or "").strip()
    t = str(title or "").strip()
    key = (re.sub(r"\s+", " ", a).casefold(),
           re.sub(r"\s+", " ", t).casefold())
    corrections = {
        # Radio misspelling; artist's original track title and Spotify listing.
        ("hvob", "the anxierty to please"): ("HVOB", "The Anxiety to Please"),
        # Corrupted encoding in RadioBox; catalog track on Pasar De Las Luces.
        ("mint field", "nada es esta?tico y evoluciona"):
            ("Mint Field", "Nada Es Estático Y Evoluciona"),
        # Radio artist is reversed surname/given-name, not a different band.
        ("cole, lloyd", "backwoods"): ("Lloyd Cole", "Backwoods"),
        # Exact featured recording, not the ordinary Cyanide studio track.
        ("daniel caesar feat. koffee", "cyanide remix"):
            ("Daniel Caesar feat. Koffee", "CYANIDE REMIX (feat. Koffee)"),
    }
    return corrections.get(key, (a, t))


def has_report_correction(artist, title):
    original = (str(artist or "").strip(), str(title or "").strip())
    return report_correction(artist, title) != original
