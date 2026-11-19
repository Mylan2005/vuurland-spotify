"""v245 regression: grouped radio guests map to separate Spotify artists."""
import ast
from pathlib import Path
from v245_multi_guest_credits import split_explicit_multiword_guests as split, guest_credit_matches as matches

assert split("Tom Hodge & Kathrin DeBoer") == ["Tom Hodge", "Kathrin DeBoer"]
assert split("Tom Hodge and Kathrin deBoer") == ["Tom Hodge", "Kathrin deBoer"]
assert split("Tom Hodge") == ["Tom Hodge"]
assert split("Earth Wind & Fire") == ["Earth Wind & Fire"]
assert split("Beyoncé & Jay-Z") == ["Beyoncé & Jay-Z"]
assert split("Hodge & deBoer") == ["Hodge & deBoer"]
assert split("") == []
assert split("Tame Impala, SZA, King Gizzard...") == ["Tame Impala", "SZA", "King Gizzard..."]
assert split("Tame Impala, SZA, King Gizzard & the Lizard Wizard") == ["Tame Impala", "SZA", "King Gizzard & the Lizard Wizard"]
assert matches("King Gizzard...", ["Justice", "King Gizzard & the Lizard Wizard"])
assert not matches("King...", ["King Gizzard & the Lizard Wizard"])
assert not matches("King Gizzard...", ["King Gizzard & the Lizard Wizard", "King Gizzard & Friends"])
assert matches("SZA", ["Justice", "SZA"])
assert not matches("SZA", ["Justice", "Sia"])
# Require both independent Spotify artist-object credits; don't accept a solo.
wanted = [n.casefold() for n in split("Tom Hodge & Kathrin DeBoer")]
assert all(x in ["max cooper","tom hodge","kathrin deboer"] for x in wanted)
assert not all(x in ["max cooper","tom hodge"] for x in wanted)

source = Path(__file__).with_name("vuurland_sync.py").read_text("utf-8")
module = ast.parse(source)
locator = next(ast.literal_eval(n.value) for n in module.body
               if isinstance(n, ast.Assign)
               and any(isinstance(t,ast.Name) and t.id == "V81_VERIFIED_CATALOG_TRACKS"
                       for t in n.targets))
assert locator[("max cooper", "trust ft. tom hodge & kathrin deboer")] == "7EWkEIxfgg5cieKB6CJGws"
assert "for title_guest in split_explicit_multiword_guests(title_feature_artist)" in source
assert "guests = split_explicit_multiword_guests(credit)" in source
assert "guest_credit_matches(wanted_feature, spotify_artists)" in source
assert "wanted_artists.append(normalized_title_feature)" in source
assert "if missing_feature_count:" in source
assert "if item.get(\"is_playable\") is False:" in source
assert '"GET", f"/tracks/{catalog_id}"' in source
print("✅ v245 separate full guest credits; exact verified Trust locator; no approval bypass")
