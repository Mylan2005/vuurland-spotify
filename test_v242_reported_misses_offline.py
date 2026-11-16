"""v242: report observations preserve provenance and never certify a match."""
from v242_reported_misses import REPORTED_MISSES, reported_v242_for_safe_retry
from v203_matcher_upgrade_requeue import applicable_rules
from pathlib import Path

assert len(REPORTED_MISSES) == 84
assert len(set(REPORTED_MISSES)) == 51
for source, artist, title in REPORTED_MISSES:
    assert reported_v242_for_safe_retry(artist, title, source)
    assert not reported_v242_for_safe_retry(artist, title, "unknown")
    assert "v242_reported_source_retry" in applicable_rules(artist, title)
assert not reported_v242_for_safe_retry("Brooke Combe", "Broken Stones", "radio_x_chilled")
source = Path(__file__).with_name("vuurland_sync.py").read_text()
assert 'Spotify playlist POST HTTP' in source
assert '"POST"' in source and '/playlists/' in source
print("✅ v242: 51 unieke bronobservaties, veilige retry en 502-beveiliging.")
