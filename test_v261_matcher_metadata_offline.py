"""Offline regressions for v261. No Spotify calls or writes."""
from pathlib import Path
from v261_matcher_metadata import abbreviated_title_feature, safe_contraction_replacement

assert abbreviated_title_feature("Are You Bored Yet? (f Clairo)") == ("Are You Bored Yet?", "Clairo")
assert abbreviated_title_feature("flowin (feat. Sam Wise)") is None
assert abbreviated_title_feature("f Clairo") is None
assert abbreviated_title_feature("Song (f DJ Mix)") is None
assert abbreviated_title_feature("Song (Live)") is None
assert abbreviated_title_feature("Song (f X)") is None
assert abbreviated_title_feature("Song (f Sam Wise)") == ("Song", "Sam Wise")
assert safe_contraction_replacement("Ill", "I'll") is None
assert safe_contraction_replacement("ill", "i'll") is None
assert safe_contraction_replacement("dont", "don't") == "don't"
assert safe_contraction_replacement("will", None) is None

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
assert "abbreviated_title_feature(raw)" in src
assert "safe_contraction_replacement(part, contractions.get(key))" in src
assert '"da ze": ["Daze"]' in src
assert '"fink uk": ["Fink"]' in src
assert '"gypsy and the cat": ["GATC"]' in src
print("v261 safe metadata tests passed")
