"""v262 regression: an exact official A x B project may be one artist object.

Spotify requests, playlist writes and queue/cache state are not involved.
"""
import ast
from pathlib import Path
from v261_matcher_metadata import exact_single_x_project_credit

assert exact_single_x_project_credit("Stimming x Lambert", ["Stimming x Lambert"])
assert exact_single_x_project_credit("Stimming   x  Lambert", ["Stimming x Lambert"])
assert exact_single_x_project_credit("stimming x lambert", ["Stimming x Lambert"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Stimming"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Lambert"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Lambert x Stimming"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Stimming", "Lambert"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Stimming x Lambert", "Other"])
assert not exact_single_x_project_credit("Stimming & Lambert", ["Stimming x Lambert"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Stimming x Lambert (Cover)"])
assert not exact_single_x_project_credit("Stimming x Lambert", [])
assert not exact_single_x_project_credit("A x B", ["A x B"])
assert not exact_single_x_project_credit("Stimming x Lambert", ["Stimming & Lambert"])

# Ensure the real production matcher applies the exact-artist alternative
# BEFORE its old two-artist guard, while keeping other validation layers.
source = Path("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
assert "v262_single_x_project_credit = bool(" in source
assert "if _v238_radio_duo and not v262_single_x_project_credit:" in source
assert "if v262_single_x_project_credit:\n            primary_artist_exact = True" in source
assert "if item.get('is_playable') is False:" in source
assert "if (item.get('restrictions') or {}).get('reason') == \"market\":" in source
print("v262 exact single-project artist gate regressions passed")
