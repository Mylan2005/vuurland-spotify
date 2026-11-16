"""v252: never queue or search unavailable Brooke Combe Radio X live track."""
from pathlib import Path
from v252_unavailable_radio_x import skip_unavailable_radio_x_recording as skip

for title in ("Broken Stones (Live at On The Beach", "Broken Stones (Live at On The Beach)",
              "broken stones (LIVE AT ON THE BEACH)"):
    assert skip("radio_x_chilled", "Brooke Combe", title), title

for source, artist, title in (
    ("big_sonic_heaven", "Brooke Combe", "Broken Stones (Live at On The Beach)"),
    ("radio_x_chilled", "Brooke Combe", "Broken Stones"),
    ("radio_x_chilled", "Brooke Combe", "Broken Stones (Studio)"),
    ("radio_x_chilled", "Other Artist", "Broken Stones (Live at On The Beach)"),
    ("radio_x_chilled", "Brooke Combe", "Broken Stones (Live at Other Beach)"),
):
    assert not skip(source, artist, title), (source, artist, title)

s = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert 'from v252_unavailable_radio_x import skip_unavailable_radio_x_recording' in s
assert "if skip_unavailable_radio_x_recording(sid, artist, title):" in s
assert "if skip_unavailable_radio_x_recording(sid, artist, title):" in s[s.index("def v96_collect_live_plays("):]
assert "if skip_unavailable_radio_x_recording(sid, artist, title):" in s[s.index("def v47_collect_radio_history("):s.index("def v96_collect_live_plays(")]
assert "and not skip_unavailable_radio_x_recording(" in s[s.index("def sync("):s.index("before_source_filter =", s.index("def sync("))+1900]
assert 'skip_unavailable_radio_x_recording(item.get("source"), artist, title)' in s
print("✅ v252: live-opname skip bij ingestie, bestaande queue en vóór Spotify Search.")
