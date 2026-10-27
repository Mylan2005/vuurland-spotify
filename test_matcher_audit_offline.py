"""Offline smoke tests for the complete historical matcher audit."""
from vuurland_matcher_audit import audit, markdown

cache = {
    "__v51_radio_failed_searches": {
        "a|||old": 4,
        "b|||parked": 5,
        "c|||done": 2,
        "d|||hint": 1,
    },
    "__v51_radio_unmatched": {"b|||parked": {"artist": "B", "title": "Parked", "source": "dkfm_edge"}},
    "__v47_failed_tracks": {"a|||old": {"artist": "A", "title": "Old"}},
    "__playlist_keys": ["c|||done"],
    "__v82_confirmed_catalog": {"d|||hint": {"id": "still_needs_validation"}},
}
rows = audit(cache)
assert len(rows) == 4
by_key = {r["key"]: r for r in rows}
assert by_key["b|||parked"]["status"] == "geparkeerd"
assert by_key["b|||parked"]["source"] == "dkfm_edge"
assert by_key["c|||done"]["status"] == "reeds_in_playlist_cache"
assert by_key["d|||hint"]["status"] == "catalogushint_te_verifieren"
assert by_key["a|||old"]["failed_searches"] == 4
assert [r["failed_searches"] for r in rows] == [5, 4, 2, 1]
assert "B — Parked" in markdown(rows)
assert audit({}) == []
try:
    audit({"__v51_radio_failed_searches": ["ongeldig"]})
except ValueError:
    pass
else:
    raise AssertionError("Ongeldige cache niet geweigerd")
print("✅ Matcher-audit: volledige historiek, status, prioriteit en robuustheid OK")
