"""v254: corrected historical misses; every version/artist protection retained."""
from pathlib import Path
from v254_verified_report_metadata import (
    report_correction, has_report_correction,
)
pairs = (
    ("HVOB", "The Anxierty to Please", "HVOB", "The Anxiety to Please"),
    ("MINT FIELD", "Nada Es Esta?tico Y Evoluciona", "Mint Field", "Nada Es Estático Y Evoluciona"),
    ("Cole, Lloyd", "Backwoods", "Lloyd Cole", "Backwoods"),
    ("Daniel Caesar feat. Koffee", "Cyanide Remix", "Daniel Caesar feat. Koffee", "CYANIDE REMIX (feat. Koffee)"),
    ("Kraftwerk 2", "Spiegelsaal", "Kraftwerk", "Spiegelsaal"),
    ("Kraftwerk 6", "Abzug", "Kraftwerk", "Abzug"),
    ("Kim Wilde", "03 Cambodia", "Kim Wilde", "Cambodia"),
)
for artist, title, want_artist, want_title in pairs:
    assert report_correction(artist, title) == (want_artist, want_title)
    assert has_report_correction(artist, title)
for artist, title in (
    ("HVOB", "The Anxiety to Please"),
    ("HVOB", "The Anxierty to Please (Live)"),
    ("Other Band", "The Anxierty to Please"),
    ("Mint Field", "Nada Es Estático Y Evoluciona"),
    ("Other", "Nada Es Esta?tico Y Evoluciona"),
    ("Lloyd Cole", "Backwoods"),
    ("Cole, Lloyd", "Backwoods (Live)"),
    ("Daniel Caesar feat. Koffee", "Cyanide"),
    ("Daniel Caesar", "Cyanide Remix"),
    ("Daniel Caesar feat. Someone Else", "Cyanide Remix"),
    ("Kraftwerk 3", "Spiegelsaal"),
    ("Kraftwerk 2", "Abzug"),
    ("Kim Wilde", "03 Cambodia (Live)"),
):
    assert report_correction(artist, title) == (artist, title), (artist, title)
    assert not has_report_correction(artist, title), (artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
matching = src[src.index("def find_spotify_track("):src.index("def add_tracks(")]
assert matching.index("v101_original_key = v101_radio_key(artist, title)") < matching.index("_v254_artist, _v254_title = v254_report_correction(artist, title)")
assert "has_unrequested_performance_modifiers(" in matching
assert "v211_version_guard(" in matching
assert "safe_remix_original_fallback(" in matching
assert "if uri in playlist_uris:" in src
requeue = Path(__file__).with_name("v203_matcher_upgrade_requeue.py").read_text(encoding="utf-8")
assert '"v254_verified_report_metadata"' in requeue
assert "if has_v254_report_correction(artist, title):" in requeue
assert "reported_for_safe_retry" in requeue
assert "_MIN_GAP = 6 * 3600" in requeue
print("✅ v254: zeven concrete radiometadata-fouten hersteld, veilige match en FIFO-herkansingen.")
