"""v242: report observations preserve provenance and never certify a match."""
from v242_reported_misses import REPORTED_MISSES, reported_v242_for_safe_retry
from v203_matcher_upgrade_requeue import applicable_rules
from pathlib import Path
from v235_general_search_rescue import alternate_remix_credit_search, rescue_search_query

assert len(REPORTED_MISSES) == 84
assert len(set(REPORTED_MISSES)) == 84
for source, artist, title in REPORTED_MISSES:
    assert reported_v242_for_safe_retry(artist, title, source)
    assert not reported_v242_for_safe_retry(artist, title, "unknown")
    assert "v242_reported_source_retry" in applicable_rules(artist, title)
assert not reported_v242_for_safe_retry("Brooke Combe", "Broken Stones", "radio_x_chilled")
assert alternate_remix_credit_search("Wilmot (Remix by Red snapper)") == "Wilmot (Red snapper Remix)"
assert alternate_remix_credit_search("Ordinary Song") is None
assert alternate_remix_credit_search("Song (Remix by X feat Y)") is None
assert "Red snapper Remix" in rescue_search_query("Sabres of paradise",
    "Wilmot (Remix by Red snapper)", '"Sabres of paradise" "Wilmot"', 1)
source = Path(__file__).with_name("vuurland_sync.py").read_text()
assert 'Spotify playlist POST HTTP' in source
assert '"POST"' in source and '/playlists/' in source
assert source.index('if _playlist_append:') < source.index('server_errors += 1')
assert '"Spotify playlist POST HTTP 502:"' in source
print("✅ v242: 84 unieke bronobservaties, veilige retry en 502-beveiliging.")
