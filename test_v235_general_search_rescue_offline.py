"""v235: zoekvormen verbreden; NEVER artiest/titel/versie match-autorisatie."""
import ast
from pathlib import Path
from v235_general_search_rescue import (
    catalog_search_artist, incomplete_parenthesis_search_core,
    rescue_search_query,
)

# Brononafhankelijk: niet alleen TRACES, maar elke volledige gespatieerde
# artiestnaam met voldoende letters.
for raw, expected in [
    ("T R A C E S", "TRACES"),
    ("A B C D", "ABCD"),
    ("S P A C E D", "SPACED"),
    ("T. R. A. C. E. S.", "T. R. A. C. E. S."),
    ("J R", "J R"),
    ("A B C", "A B C"),
    ("A B C & D", "A B C & D"),
    ("The A B C D", "The A B C D"),
    ("R E M I X 2025", "R E M I X 2025"),
]:
    assert catalog_search_artist(raw) == expected, raw

for raw, expected in [
    ('The Big Pink - Sweet Dreams (Beyonce', 'The Big Pink - Sweet Dreams'),
    ('Sweet Dreams (Beyonce', 'Sweet Dreams'),
    ('Under The Stars (Wilkinson Remix', 'Under The Stars'),
    ('Pictures (GZUS Remix', None), # One-word core: don't overbroaden
    ("I'd Rather Be With You (Radio", "I'd Rather Be With You"),
    ('First Time High (Reconstructionist Remix of "An Eluardian In', 'First Time High'),
    ('Beyonce (Live)', None),
    ('Badlands (Live from Sirius XM)', None),
    ('Live (Radio', None),
    ('Run (Radio', None),
    ('(Intro', None),
    ('A Long Song (Live) (BBC', 'A Long Song'),
]:
    assert incomplete_parenthesis_search_core(raw) == expected, (raw, expected)

# Eerste zoekbeurt blijft volledig origineel, de bestaande tweede/derde
# zoekbeurt krijgt een bredere route met volledige artist- en kerntitel.
q = 'artist:"Morning Parade" track:"Under The Stars (Wilkinson Remix"'
assert rescue_search_query("Morning Parade", "Under The Stars (Wilkinson Remix", q, 0) == q
assert rescue_search_query("Morning Parade", "Under The Stars (Wilkinson Remix", q, 1) == '"Morning Parade" "Under The Stars"'
assert rescue_search_query("Morning Parade", "Under The Stars (Wilkinson Remix", q, 2) == '"Morning Parade" "Under The Stars"'
assert rescue_search_query("The Charlottes", "Keep Me Down (Album Version)", "original query", 1) == "original query"
assert rescue_search_query("Beyonce", "Dreams (Live)", "original query", 2) == "original query"
assert rescue_search_query("T R A C E S", "conceal", "T R A C E S conceal", 0) == "TRACES conceal"

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
matcher = ast.get_source_segment(source, next(node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "find_spotify_track"))
assert matcher.index("v101_original_key") < matcher.index("v235_search_artist(spotify_search_artist)")
assert matcher.index("v235_rescue_query(") < matcher.index('"/search"')
assert matcher.index("v235_rescue_query(") < matcher.index("primary_artist_exact")
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
print("✅ v235: brede veilige zoekhints; remix/live-verificatie en Spotify-quota ongewijzigd.")
