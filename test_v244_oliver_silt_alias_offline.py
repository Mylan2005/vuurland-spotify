"""Offline regression: confirmed Oliver Beardmore -> silt. artist credit."""
import ast
import pathlib

source = pathlib.Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
module = ast.parse(source)
aliases = next(ast.literal_eval(node.value) for node in module.body
               if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "ARTIST_ALIASES"
                       for target in node.targets))
assert aliases["oliver beardmore"] == ["silt."]
assert "oliver beardmore" not in aliases.get("silt", [])
assert "search_artist_aliases = ARTIST_ALIASES.get(" in source
assert "spotify_search_artist = (" in source
assert "wanted_names.update(str(alias) for alias in search_artist_aliases)" in source
assert "if alias_artist_match:" in source
assert "primary_artist_exact = True" in source
assert "has_unrequested_performance_modifiers" in source
assert "v211_version_guard(" in source
print("✅ v244 Oliver Beardmore -> silt. future source alias, strict candidate guards.")
