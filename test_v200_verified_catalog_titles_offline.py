"""v200 offline regressions: only verified complete artist/title can match."""
import ast
from pathlib import Path
from v200_verified_catalog_titles import verified_catalog_title

assert verified_catalog_title("Tired Pony", "All Things At Once", "All Things All At Once")
assert verified_catalog_title("TIRED PONY", "all things at once", "All Things All At Once")
assert not verified_catalog_title("Tired Pony", "All Things At Once", "All Things All At Once - Live")
assert not verified_catalog_title("Tired Pony", "All Things At Once", "All Things All At Once Remix")
assert not verified_catalog_title("Tired Pony", "All Things At Once", "All Things Once")
assert not verified_catalog_title("Tired Pony", "All Things", "All Things All At Once")
assert not verified_catalog_title("Tired Pony Tribute Band", "All Things At Once", "All Things All At Once")
assert not verified_catalog_title("Another Band", "All Things At Once", "All Things All At Once")
assert not verified_catalog_title("Tired Pony", "All Things At Once (Live)", "All Things All At Once")
assert not verified_catalog_title("Hyper Nova", "Lost In Space", "Hypernova Skies")
assert not verified_catalog_title("The Decemberists", "Rise To Me", "Rise To Me - Live")
assert not verified_catalog_title("The Decemberists", "Rise To Me", "Rise To Me")

source = (Path(__file__).parent / "vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
i = source.index("verified_catalog_variant = (")
j = source.index("structural_title_match = (", i)
guard = source[i:j]
assert "primary_artist_exact" in guard
assert "wanted_version == spotify_version" in guard
assert "v200_verified_catalog_title(" in guard
# v211 voegt alleen een nieuwe exacte variant TOE vóór de bestaande regel.
# De structurele prioriteitsketen moet de oude veilige controles behouden.
assert "or truncated_title_match" in source[j:j+450]
assert "max_additions_per_round = 1" in source
print("✅ v200: exact Tired Pony rescue and existing version/FIFO safety gates.")
