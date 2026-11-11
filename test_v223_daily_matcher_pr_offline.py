"""Offline safety checks for v223 daily matcher proposal, no Spotify calls."""
import ast
import json
import tempfile
from pathlib import Path
from v223_daily_matcher_proposal import build, suggested_hints
from v223_report_search_hints import load_hints, report_third_search_hint

base = Path(__file__).with_name("v223_matcher_search_hints.json")
assert load_hints(base) == {}
assert report_third_search_hint("Any", "Song", 2) is None
assert report_third_search_hint("Any", "Song", 0) is None

def row(artist, title, source, reports=2, candidate=None):
    return {
        "artist": artist, "title": title, "source": source,
        "run_reports": reports,
        "category": "gelijke_artiest_en_titel_nader_controleren",
        "preview_candidates": [{"artist": candidate or artist, "title": title}],
    }

report = {"records": [
    row("The Decemberists", "Rise To Me", "indie_select", 3),
    row("The National", "Fake Empire (Live)", "dark_edge", 5),
    row("Artist One", "Real Song", "missing_radio", 5),
    row("Artist Two", "Real Song", "dark_edge", 1),
    row("Artist Three", "Other Song", "duyster", 5, candidate="Wrong Artist"),
    row("Artist Four", "Third Song", "dkfm_shoegaze", 2),
]}
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "hints.json"
    path.write_text(base.read_text(encoding="utf-8"), encoding="utf-8")
    before = path.read_text()
    proposals, additions = build(report, path)
    assert before == path.read_text()  # never auto-edit active registry
    assert len(additions) == 2
    assert [r["artist"] for r in additions] == ["The Decemberists", "Artist Four"]
    path.write_text(json.dumps(proposals), encoding="utf-8")
    loaded = load_hints(path)
    assert loaded[("the decemberists", "rise to me")] == '"The Decemberists" "Rise To Me"'
    assert loaded[("artist four", "third song")] == '"Artist Four" "Third Song"'
    assert not suggested_hints(report, proposals)
    modified = json.loads(path.read_text())
    modified["hints"][0]["independent_reports"] = 1
    path.write_text(json.dumps(modified))
    try:
        load_hints(path)
        raise AssertionError("Unsafe report count allowed")
    except ValueError:
        pass

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
assert 'elif search_variant == 2:' in src
assert 'v223_report_query(*v101_original_key, search_variant)' in src
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in src
assert 'max_additions_per_round = 1' in src
assert 'MAX_SEARCHES_PER_RUN = 1' in src
assert 'v217_report_query(*v101_original_key, search_variant)' in src
assert 'v203_release_matcher_upgrade(' in src
assert 'fair_source_candidates(' in src
print("✅ v223: daily review PR hints scoped to third query, no auto approval or extra Search.")
