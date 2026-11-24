"""Verified Turkish-language vocal ban; country and genre never decide language."""
import ast
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text("utf-8")
tree = ast.parse(src)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
assignment = next(
    node for node in tree.body
    if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == "V263_CONFIRMED_TURKISH_VOCALS"
        for target in node.targets)
)
pairs = frozenset(ast.literal_eval(assignment.value.args[0]))
ns = {"V263_CONFIRMED_TURKISH_VOCALS": pairs}
exec(compile(ast.Module(body=[functions["v263_is_confirmed_turkish_vocal"]],
                        type_ignores=[]), "<turkish-vocals>", "exec"), ns)
confirmed = ns["v263_is_confirmed_turkish_vocal"]
assert confirmed("Sren", "Bozuk")
assert confirmed(" SREN ", " BOZUK ")
assert not confirmed("Sren", "Different Song")
assert not confirmed("Different Artist", "Bozuk")
assert not confirmed("Turkish Artist", "English Language Song")
# Confirmation precedes both language exemptions and Spotify search.
assert "if v263_is_confirmed_turkish_vocal(artist, title):\n        return True" in src
assert "if v263_is_confirmed_turkish_vocal(artist, title):\n        return \"block\"" in src
assert '("blokkeren", "block", "duits", "turks", "turkish")' in src
assert src.index("if v263_is_confirmed_turkish_vocal(artist, title):\n        return True") < src.index("def v106_language_decision(")
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
print("✅ Turkse zang: gecontroleerde opnames blokkeren; geen nationaliteitsgok of Spotify-omweg")
