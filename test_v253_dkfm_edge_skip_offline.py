"""v253: prevent repeated Spotify attempts for DKFM Edge The Veldt – Angel Heart."""
from pathlib import Path
from v253_unavailable_dkfm_edge import skip_unavailable_dkfm_edge_recording as skip

assert skip("dkfm_edge", "The Veldt", "Angel Heart")
assert skip("dkfm_edge", "the veldt", " ANGEL   HEART ")
for source, artist, title in (
    ("dkfm_classic", "The Veldt", "Angel Heart"),
    ("big_sonic_heaven", "The Veldt", "Angel Heart"),
    ("dkfm_edge", "The Veldt", "Another Heart"),
    ("dkfm_edge", "The Veldt", "Angel Heart (Live)"),
    ("dkfm_edge", "The Veldt", "Angel Heart Remix"),
    ("dkfm_edge", "Other Band", "Angel Heart"),
    ("dkfm_edge", "The Veldt", "Angel Heartbeat"),
):
    assert not skip(source, artist, title), (source, artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert "from v253_unavailable_dkfm_edge import skip_unavailable_dkfm_edge_recording" in src
assert "or skip_unavailable_dkfm_edge_recording(sid, artist, title)" in src
assert src.count("or skip_unavailable_dkfm_edge_recording(sid, artist, title)") == 2
assert "and not skip_unavailable_dkfm_edge_recording(" in src
assert 'skip_unavailable_dkfm_edge_recording(item.get("source"), artist, title)' in src
assert 'if uri in playlist_uris:' in src
print("✅ v253: DKFM Edge The Veldt Angel Heart exact uitgesloten; andere tracks blijven normaal.")
