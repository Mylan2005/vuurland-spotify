"""v217: report #48 third-search recall. Entirely offline."""
import ast
from pathlib import Path
from v217_report_search import report_third_search_query as query, has_report_search_rescue
from v203_matcher_upgrade_requeue import applicable_rules

expected = {
    ("Comsat Angels", "Shiva Descending"): '"Comsat Angels" "Shiva Descending"',
    ("eyelash", "Strawberry"): '"eyelash" "Strawberry"',
    ("Fragile Animals", "Breathe Out And In"): '"Fragile Animals" "Breathe Out And In"',
    ("Hatchie", "Eyes Without A Face"): '"Hatchie" "Eyes Without A Face"',
    ("Loom", "Slowmotion"): '"Loom" "Slowmotion"',
    ("More Earth Than Sea", "Alone Again"): '"More Earth Than Sea" "Alone Again"',
    ("Phosphene", "Black Sheep"): '"Phosphene" "Black Sheep"',
    ("Shout Out Louds", "Hard Rain (Live from Haldern Festival)"):
        '"Shout Out Louds" "Hard Rain" "Haldern"',
    ("Tombstones In Their Eyes", "Fall"): '"Tombstones In Their Eyes" "Fall"',
    ("Ultra Vivid scene", 'Mercy seat (12")'): '"Ultra Vivid Scene" "Mercy Seat"',
    ("Virgins", "s o f t e r"): '"Virgins" "softer"',
}
assert len(expected) == 11
for (artist, title), q in expected.items():
    assert query(artist, title, 2) == q
    assert query(artist, title, 0) is None
    assert query(artist, title, 1) is None
    assert "v217_report_independent_third_search" in applicable_rules(artist, title)

for artist, title in (
    ("Hatchie", "Eyes Without A Face (Live)"),
    ("Billy Idol", "Eyes Without A Face"),
    ("Loom", "Slowmotion (Acoustic)"),
    ("Virgins", "s o f t e r (Demo)"),
    ("Comsat Angels", "Another Song"),
    ("Tombstones In Their Eyes", "Fallen"),
    ("Shout Out Louds", "Hard Rain"),
    ("Ultra Vivid Scene", "Mercy Seat (Live)"),
    ("!!! (Chk Chk Chk)", "AM/FM"),  # separately covered by v216
):
    assert query(artist, title, 2) is None
    assert not has_report_search_rescue(artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf8")
tree = ast.parse(src)
matcher = ast.get_source_segment(src, next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "find_spotify_track"
))
assert "v217_report_query(*v101_original_key, search_variant)" in matcher
assert matcher.index("v217_report_query(") < matcher.index('data = spotify_request(\n            "GET",\n            "/search"')
assert matcher.index("v217_report_query(") < matcher.index("v211_version_guard(")
assert "has_unrequested_performance_modifiers(" in matcher
assert "candidate_isrc" in matcher
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in src
assert 'MAX_SEARCHES_PER_RUN = 1' in src
assert 'max_additions_per_round = 1' in src
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in src
print("✅ v217: eleven narrow third-query rescues; existing Spotify, version, FIFO guards intact.")
