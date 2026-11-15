"""Offline regression tests for the v241 final-'s' catalog rescue."""
from v241_final_plural_rescue import (
    final_s_candidate_title, safe_final_plural_equivalent as same,
)
from v235_general_search_rescue import rescue_search_query
from v203_matcher_upgrade_requeue import applicable_rules

def equivalent(a, b, *, artist=True, all_guests=True, version=None, candidate_version=None):
    return same(
        a, b, primary_artist_exact=artist, all_credits_present=all_guests,
        wanted_version=version, catalog_version=candidate_version,
    )

# The real observed difference is only one final s in a multiword title.
assert final_s_candidate_title("Chalk Tablet Tower") == "Chalk Tablet Towers"
assert final_s_candidate_title("Chalk Tablet Towers") is None
assert final_s_candidate_title("Holy War - Other Artist") is None
assert final_s_candidate_title("Chalk Tablet Tower (Radio Edit)") is None
assert final_s_candidate_title("Sun") is None
assert final_s_candidate_title("Red Velvet (Blue Remix)") is None
assert final_s_candidate_title("Boy From School (Hot Chip Cover)") is None
assert final_s_candidate_title("Stranger Things Theme (Extended)") is None

assert equivalent("Chalk Tablet Tower", "Chalk Tablet Towers")
assert equivalent("Chalk Tablet Towers", "Chalk Tablet Tower")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towerz")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towering")
assert not equivalent("Chalk Tablet Tower", "Another Tablet Towers")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablets Tower")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towers", artist=False)
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towers", all_guests=False)
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towers", version="live")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towers", candidate_version="remix")
assert not equivalent("The Tower", "The Towers")
assert not equivalent("Hello Stranger", "Hello Strangers")
assert not equivalent("My Heart Is Strong", "My Heart Is Stronger")
assert not equivalent("Chalk Tablet Tower", "Chalk Tablet Towers", version="remix", candidate_version="live")

# No extra Spotify HTTP request: only replace the already scheduled variant.
assert rescue_search_query("Gorillaz", "Chalk Tablet Tower", "original", 0) == "original"
assert rescue_search_query("Gorillaz", "Chalk Tablet Tower", "original", 1) == '"Gorillaz" "Chalk Tablet Towers"'
assert "v241_final_plural_title" in applicable_rules("GORILLAZ FEAT. ST. VINCENT", "Chalk Tablet Tower")
assert "v241_final_plural_title" not in applicable_rules("Gorillaz", "Chalk Tablet Towers")
print("✅ v241: final-s metadata search, strict artist/guests/version identity, safe FIFO eligibility")
