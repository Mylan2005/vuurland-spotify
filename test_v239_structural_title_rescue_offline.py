"""Offline regression checks for structural search recalls; no Spotify requests."""
from v239_structural_title_rescue import safe_search_title, structural_recording_equivalent as same, explicit_dual_feature_names
from v235_general_search_rescue import rescue_search_query

def equivalent(left, right, req=None, cand=None, exact=True):
    return same(left, right, primary_artist_exact=exact,
                requested_version=req, candidate_version=cand)

assert safe_search_title("Kyle Dixon & Michael Stein", "Stranger Things Theme (Extended)", 0) is None
assert safe_search_title("Kyle Dixon & Michael Stein", "Stranger Things Theme (Extended)", 1) == "Stranger Things Extended"
assert safe_search_title("Seekae", "3 (Three)", 1) == "3"
assert safe_search_title("Seekae", "4 (Three)", 1) is None
assert safe_search_title("Blush", "Blush-Lover-s-Speed", 1) == "Blush-Lover's Speed"
assert safe_search_title("Fenech-Soler", "Lies (Original)", 1) == "Lies"
assert safe_search_title("Grizzly Bear", "Boy From School (Hot Chip Cover)", 1) is None

assert equivalent("Stranger Things Theme (Extended)", "Stranger Things - Extended", "extended", "extended")
assert equivalent("Stranger Things - Extended", "Stranger Things Theme (Extended)", "extended", "extended")
assert not equivalent("Stranger Things Theme (Extended)", "Stranger Things", "extended", None)
assert not equivalent("Stranger Things Theme (Extended)", "Stranger Things - Live", "extended", "live")
assert not equivalent("Stranger Things Theme (Extended)", "Stranger Things - Extended", "extended", "extended", False)
assert not equivalent("Theme (Extended)", "Theme - Extended", "extended", "extended")
assert not equivalent("Unknown Theme (Extended)", "Unknown - Extended", "extended", "extended")
assert not equivalent("Stranger Things Theme (Extended)", "Another Things - Extended", "extended", "extended")
assert equivalent("3 (Three)", "3", None, None)
assert not equivalent("3 (Three)", "4", None, None)
assert not equivalent("3 (Three)", "3 - Live", None, "live")
assert not equivalent("4 (Three)", "4", None, None)
assert not equivalent("Boy From School (Hot Chip Cover)", "Boy From School", None, None)
assert not equivalent("Red Velvet (Yellow Then Blue Remix)", "Red Velvet", "remix", None)

query = rescue_search_query("Kyle Dixon & Michael Stein",
    "Stranger Things Theme (Extended)", "initial", 1)
assert query == '"Kyle Dixon & Michael Stein" "Stranger Things Extended"'
assert rescue_search_query("Seekae", "3 (Three)", "initial", 1) == '"Seekae" "3"'
assert rescue_search_query("Fenech-Soler", "Lies (Original)", "initial", 0) == "initial"
print("✅ v239: guarded soundtrack, number, apostrophe and original-version search tests")

# Full guest-credit splitting is guarded by the caller's explicit feat marker.
assert explicit_dual_feature_names("Sufjan Stevens & Rebecca Sugar") == ("Sufjan Stevens", "Rebecca Sugar")
assert explicit_dual_feature_names("Alex Landon") is None
assert explicit_dual_feature_names("Hare Squead") is None
assert explicit_dual_feature_names("Angus & Julia") is None
assert explicit_dual_feature_names("Lady Gaga & Rebecca Sugar") == ("Lady Gaga", "Rebecca Sugar")

from pathlib import Path
source = Path(__file__).with_name("vuurland_sync.py").read_text("utf-8")
assert "guests = v240_dual_feature(credit)" in source
assert "expanded.extend(guests)" in source
assert "for guest_index, wanted_feature in enumerate(wanted_artist_compact[1:], start=1):" in source
