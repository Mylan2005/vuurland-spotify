"""v215: reject wrong compound versions; never weaken artist/title checks."""
import ast
from pathlib import Path

from v215_multi_version_guard import (
    _explicit_modifiers,
    has_unrequested_performance_modifiers as rejects,
)

# Extra qualifiers in Spotify candidate are never the requested recording.
for requested, candidate in (
    ("Song (Live)", "Song - Live Acoustic"),
    ("Song (Live)", "Song (Live Remix)"),
    ("Song - Acoustic", "Song (Live Acoustic)"),
    ("Song (Acoustic)", "Song (Acoustic Demo)"),
    ("Song (Demo)", "Song (Demo Remix)"),
    ("Song (Live at BBC)", "Song - Live at BBC - Radio Edit"),
    ("Song (Instrumental)", "Song (Instrumental Karaoke)"),
    ("Song (Live)", "Song (Live) - Taylor's Version"),
    ("Song (Live)", "Song (Live, Sped Up)"),
    ("Song (Live)", "Song (Live) [Slowed + Reverb]"),
    ("Song (Live)", "Song (Live) - Nightcore"),
    ("Song (Acoustic Mix)", "Song (Acoustic Remix)"),
):
    assert rejects(requested, candidate), (requested, candidate)

# Identical requirements or harmless remaster notes are not rejected.
for requested, candidate in (
    ("Song (Live)", "Song (Live) - Remastered 2015"),
    ("Song (Live Acoustic)", "Song (Live Acoustic) - Remastered"),
    ("Song [Acoustic]", "Song - Acoustic"),
    ("Song (Live at BBC)", "Song (Live at BBC)"),
    ("Song - Demo", "Song (Demo)"),
    ("Song (Mix)", "Song (Mix)"),
    ("Song", "Song (Live)"),  # existing fallback/scoring is still in charge
    ("Live Through This", "Live Through This"),
    ("The Demo", "The Demo - Remastered"),
):
    assert not rejects(requested, candidate), (requested, candidate)

assert _explicit_modifiers("Live Through This") == frozenset()
assert _explicit_modifiers("Song (Live) - Acoustic") == frozenset({"live", "acoustic"})
assert _explicit_modifiers("Song (Live) - Remastered") == frozenset({"live"})

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
matcher = src[src.index("def find_spotify_track("):src.index("def spotify_search", src.index("def find_spotify_track("))]
guard = 'if has_unrequested_performance_modifiers(title, item.get("name", "")):\n            continue'
assert guard in matcher
assert matcher.index(guard) < matcher.index("v211_version_guard(")
assert matcher.index(guard) < matcher.index("structural_title_match =")
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in src
print("✅ v215: compound live/acoustic/remix/demo versions guarded; 1 Search and existing FIFO untouched.")
