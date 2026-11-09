"""v216: test exact metadata rescue from real 2026-11-09 matcher report.

No Spotify calls, no invented links, no weakening of title/version/credit
validation. All corrections are source/track scoped; other releases unchanged.
"""
import ast
from pathlib import Path

from v216_report_metadata import report_metadata_correction as fix, has_report_correction
from v203_matcher_upgrade_requeue import applicable_rules

known = {
    ("!!! (Chk Chk Chk)", "AM/FM"): ("!!!", "AM/FM"),
    ("Cole, Lloyd", "Backwoods ( Reprise )"): ("Lloyd Cole", "Backwoods (Reprise)"),
    ("Hayien", "Hayien - Somehow I Still Manage"): ("Hayien", "Somehow I Still Manage"),
    ("Oeil", "Quiet Lights (2:00 AM Version)"): ("Oeil", "Quiet Lights (2: 00 AM Version)"),
    ("Slowdive", "Avalyn 1"): ("Slowdive", "Avalyn I"),
    ("Glen Hansard Featuring Eddie Vedder & Jake Clemons", "Drive All Night"):
        ("Glen Hansard feat. Eddie Vedder feat. Jake Clemons", "Drive All Night"),
    ("TUCKER ZIMMERMAN feat BIG THIEF, TWAIN & IJI", "Burial at sea"):
        ("Tucker Zimmerman feat. Big Thief feat. Twain feat. Iji", "Burial at sea"),
}
assert len(known) == 7
for (artist, title), corrected in known.items():
    assert fix(artist, title) == corrected
    assert has_report_correction(artist, title)
    assert "v216_report_exact_metadata" in applicable_rules(artist, title)

# Never guess a correction based on substrings or similar artist/title.
for artist, title in (
    ("Another Artist", "Avalyn 1"),
    ("Slowdive", "Avalyn 2"),
    ("Slowdive", "Avalyn (Live)"),
    ("Glen Hansard Featuring Eddie Vedder & Jake Clemons", "Another Song"),
    ("Cole, Lloyd", "Backwoods (Live)"),
    ("Oeil", "Quiet Lights (3:00 AM Version)"),
    ("Hayien", "Hayien - Somehow I Still Manage (Live)"),
    ("Tucker Zimmerman feat Big Thief, Twain & Iji", "Burial at sea (Live)"),
    ("!!!", "Other Song"),
    ("Fin del Mundo", "El día de las flores (single - feat. Eterna Inocencia)"),
    ("Bill Callahan", 'Strange Trouble (feat. Bonnie "Prince" Billy)'),
    ("The Comsat Angels", "High Tide"),
):
    assert fix(artist, title) == (artist, title), (artist, title)
    assert "v216_report_exact_metadata" not in applicable_rules(artist, title)

# Corrections cannot be used as URI approvals: full matcher and version
# gates are still executed *after* source-specific normalization.
src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
matcher = ast.get_source_segment(src, next(
    n for n in ast.parse(src).body
    if isinstance(n, ast.FunctionDef) and n.name == "find_spotify_track"))
assert "v216_report_correction(artist, title)" in matcher
assert matcher.index("v216_report_correction(artist, title)") < matcher.index("v194_canonical_artist(artist)")
assert matcher.index("v216_report_correction(artist, title)") < matcher.index('data = spotify_request(\n            "GET",\n            "/search"')
assert matcher.index("v216_report_correction(artist, title)") < matcher.index("has_unrequested_performance_modifiers(")
assert "v211_version_guard(" in matcher
assert "candidate_isrc" in matcher
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in src

print("✅ v216: zeven exacte rapportcorrecties, veilige herpogingen en alle Spotify-guards behouden.")
