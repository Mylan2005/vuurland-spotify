"""v255: confirmed studio catalog queries and Search 5xx without global pause."""
from pathlib import Path
from v255_catalog_rescue import (
    catalog_metadata as metadata,
    safe_catalog_album_query as query,
    catalog_verified_retry as retry,
)
assert metadata("Martin Kohlstedt", "ELL (Christian Löffler Rework)") == (
    "Martin Kohlstedt", "ELL - Christian Loeffler Rework")
assert metadata("Elbow", "On a Day Like This") == ("Elbow", "One Day Like This")
assert metadata("Chicane vs. Natasha Bedingfield", "Bruised Water (Michael Woods Edit)") == (
    "Chicane feat. Natasha Bedingfield", "Bruised Water - Michael Woods Edit")
for artist, title, album in (
    ("Curve", "Chinese Burn", "Come Clean"),
    ("Palace Brothers", "You Will Miss Me When I Burn", "Days in the Wake"),
    ("Beady Eye", "For Anyone", "Different Gear, Still Speeding"),
    ("Sarah Harmer", "Lodestar", "You Were Here"),
):
    assert query(artist, title, 0) is None
    assert query(artist, title, 1) == f'"{artist}" "{title}" "{album}"'
    assert retry(artist, title)
for artist, title in (
    ("Curve", "Chinese Burn - Lunatic Calm Mix"),
    ("Curve", "Chinese Burn (Live)"),
    ("Other Band", "Chinese Burn"),
    ("Beady Eye", "For Anyone (Remix)"),
    ("Sarah Harmer", "Lodestar (Live)"),
    ("Donavon Frankenreiter & Jack Johnson", "Free"),
    ("Palace Brothers", "You Will Miss Me When I Burn (Live)"),
    ("Martin Kohlstedt", "ELL (Other Rework)"),
    ("Elbow", "One Day Like This"),
    ("Other Band", "On a Day Like This"),
    ("Chicane vs. Natasha Bedingfield", "Bruised Water (Original Radio Edit)"),
    ("Chicane vs. Natasha Bedingfield", "Bruised Water (Michael Woods Remix Dub)"),
    ("Chicane", "Bruised Water (Michael Woods Edit)"),
):
    assert metadata(artist, title) == (artist, title)
    assert query(artist, title, 1) is None
    assert not retry(artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
matching = src[src.index("def find_spotify_track("):src.index("def add_tracks(")]
assert matching.index("v101_original_key = v101_radio_key(artist, title)") < matching.index("v255_catalog_metadata(artist, title)")
assert "query = v255_catalog_album_query(*v101_original_key, search_variant) or query" in matching
assert "v211_version_guard(" in matching
assert "has_unrequested_performance_modifiers(" in matching
assert "safe_remix_original_fallback(" in matching
api = src[src.index("def spotify_request("):src.index("\ndef get_playlist(",src.index("def spotify_request("))]
assert 'cache["__spotify_server_error_until"] = max(' not in api[api.index("if is_search:",api.index("if response.status_code in (500, 502, 503, 504):")):api.index("server_errors += 1")]
assert "Spotify Search HTTP" in api
sync = src[src.index("def sync("):]
assert "if v255_search_server_failure(error):" in sync
assert 'live_queue.append(live_queue.pop(0))' in sync
assert 'item["_v34_retry_at"] = int(time.time()) + 3600' in sync
r = Path(__file__).with_name("v203_matcher_upgrade_requeue.py").read_text(encoding="utf-8")
assert "v255_catalog_verified_retry" in r
assert '"v255_catalog_verified_retry"' in r
assert "_MIN_GAP = 6 * 3600" in r
print("✅ v255: albumgerichte bestaande retry, veilige matcher, Spotify Search 5xx zonder globale pauze.")
