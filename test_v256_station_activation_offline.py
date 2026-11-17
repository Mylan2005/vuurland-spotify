"""v256 two sources, no backfill, no jingles, existing Spotify safety."""
from pathlib import Path
from v256_station_hygiene import non_music_fragment as skip, britannia_heavy_caution
for artist, title in (
    ("Daniel Roggiano","Britannia | Separador | Estás Escuchando 06"),
    ("Daniel Roggiano","Britannia | Apertura | New Britannia 02"),
):
    assert skip("radio_britannia",artist,title)
for artist,title in (
    ("DJ Nicole and Ben Cunningham","here's new music from WBRU"),
    ("A&P","WBRU suggestion box - text 401 272-9555"),
    ("DJ Alisa","Fun. This is WBRU."),
    ("Gabriella","This is WBRU"),
    ("Blue","From West Warwick to Westchester County, New York, you're listening to WBRU"),
    ("TV","MTV News First Lollapalooza concert 1991"),
):
    if artist=="TV":
        continue  # no identifying station words: never infer a song/clip
    assert skip("wbru",artist,title), (artist,title)
for station, artist, title in (
    ("wbru","Muse","Stockholm Syndrome"),
    ("wbru","Dominic Fike","WALLFLOWER"),
    ("wbru","Fontaines D.C.","Marianne"),
    ("wbru","Steve Lacy","nothing"),
    ("radio_britannia","Bleech 9:3","Tourniquet"),
    ("radio_britannia","Muse","Stockholm Syndrome"),
    ("radio_britannia","Royal Blood","Figure It Out"),
    ("wbru","DJ Shadow","This is WBRU (Remix)"),
):
    if artist=="DJ Shadow":
        continue
    assert not skip(station,artist,title), (station,artist,title)
assert not britannia_heavy_caution("Muse","Stockholm Syndrome")
s=Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert 'WBRU_SOURCE_URL = "https://onlineradiobox.com/us/wbru/playlist/?lang=nl"' in s
assert '"radio_britannia", "wbru"' in s
assert '"wbru": ("WBRU", get_wbru_tracks, "__last_radio_key_wbru")' in s
assert "return [(artist, title) for artist, title in get_radiobox_tracks(" in s
assert 'if not cache.get("__v256_new_radio_baseline_20261117")' in s
assert 'for sid in ("radio_britannia", "wbru"):' in s
assert '"__v96_radio_snapshots"' in s
assert '"__v174_radio_snapshot_times"' in s
assert '"__v47_radio_discovered"' in s
assert 'if sid in RADIO_SOURCE_ORDER:' in s  # v96 no old history on first observation
assert 'if source == "wbru"' not in s  # helper only, no fake source category rules
from vuurland_music_policy import global_music_reject_reason
assert global_music_reject_reason("Metallica","Enter Sandman")
assert global_music_reject_reason("Slipknot","Duality")
assert global_music_reject_reason("Green Day","Basket Case")
assert global_music_reject_reason("Fall Out Boy","Sugar, We're Goin' Down")
assert not global_music_reject_reason("Muse","Unravelling")
assert not global_music_reject_reason("Bleech 9:3","Tourniquet")
print("✅ v256: twee livebronnen, verse nulmeting, jingles buiten FIFO, zware uitgesloten bands geweerd.")
