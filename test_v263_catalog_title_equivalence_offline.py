"""v263 regression: title connector spelling only with exact credits/edition."""
import ast
from pathlib import Path
from v261_matcher_metadata import equivalent_catalog_connector_title as equiv

assert equiv("Sticks and Stones", "Sticks 'N' Stones")
assert equiv("Sticks and Stones", "Sticks ’N’ Stones")
assert equiv("Are You OK?", "Are You Okay?")
assert equiv("Are You Okay?", "Are You OK?")
assert not equiv("Stay N Go", "Stay and Go")  # bare N is not a connector
assert not equiv("Sticks and Stones", "Sticks 'N' Stones - Live")
assert not equiv("Are You OK?", "Are You Okay? (Live)")
assert not equiv("Sticks and Stones", "Sticks and Stones - Remix")
assert not equiv("Love You", "Love You Too")
assert not equiv("Stay", "Stay")
assert not equiv("No", "No")
assert not equiv("Ill", "I'll")
assert not equiv("GAS Zauberberg I", "GAS Zauberberg 3")
source = Path("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
assert "v263_catalog_title_equivalent = bool(" in source
assert "and missing_feature_count == 0" in source
assert "and wanted_version == spotify_version" in source
assert "and not solo_collab_fallback" in source
assert "or v241_plurals_match" in source
from v203_matcher_upgrade_requeue import applicable_rules
assert "v263_complete_title_spelling" in applicable_rules("Jamie T", "Sticks and stones")
assert "v263_complete_title_spelling" in applicable_rules("Dum Dum Girls", "Are You OK?")
assert "v263_complete_title_spelling" not in applicable_rules("Jamie T", "Sticks 'N' Stones - Live")
assert "v263_complete_title_spelling" not in applicable_rules("Wrong Artist", "Are You OK?")
print("v263 safe full-title catalog spelling tests passed")
