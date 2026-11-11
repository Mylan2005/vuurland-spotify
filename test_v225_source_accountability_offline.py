"""v225: regressie van echte brontoewijzing in het gezondheidsrapport."""
import pathlib
import tempfile
import os
from bronrapport_v138 import assess

with tempfile.TemporaryDirectory() as folder:
    base = pathlib.Path(folder)
    log = base / "run.log"
    queue = base / "queue.json"
    log.write_text("""📻 Vuurland sync
🔢 v221 bronrotatie: FIFO-volgnummer 6331 geselecteerd (bron: dreampop_radio).
🎯 v224 Spotify-zoekbeurt: dreampop_radio
⚠️ Geen betrouwbare Spotify-match gevonden: Decemberists, The - Rise To Me
🔢 v221 bronrotatie: FIFO-volgnummer 6246 geselecteerd (bron: indie_select).
🎯 v224 Spotify-zoekbeurt: indie_select
🎯 v224 Spotify-toevoegbeurt: indie_select
✅ Toegevoegd: The Notwist - Kong
🔢 v221 bronrotatie: FIFO-volgnummer 9087 geselecteerd (bron: dkfm_classic).
🎯 v224 Spotify-zoekbeurt: dkfm_classic
⚠️ Geen betrouwbare Spotify-match gevonden: Veldt - End All To Be All
🔢 v221 bronrotatie: FIFO-volgnummer 9098 geselecteerd (bron: dkfm_classic).
🎯 v224 Spotify-toevoegbeurt: dkfm_classic
✅ Toegevoegd: The Suncharms - One I See
""", encoding="utf-8")
    queue.write_text('[{"source":"dreampop_radio","_v116_fifo_seq":1},{"source":"dkfm_classic","_v116_fifo_seq":2},{"source":"indie_select","_v116_fifo_seq":3}]', encoding="utf-8")
    before = pathlib.Path.cwd()
    try:
        os.chdir(folder)
        rounds, seen, ok, added, counts = assess(str(log), str(queue))
        report = pathlib.Path("vuurland_brongezondheid.md").read_text(encoding="utf-8")
    finally:
        os.chdir(before)
    assert rounds == 1
    assert added["indie_select"] == 1, added
    assert added["dkfm_classic"] == 1, added
    assert added["dreampop_radio"] == 0, added
    assert "| Dreampop Radio | 0 | 0 | 1 | 1 | 0 | 1 |" in report
    assert "| DKFM Classic | 0 | 0 | 1 | 1 | 1 | 1 |" in report
    assert "| Indie Select | 0 | 0 | 1 | 0 | 1 | 1 |" in report

print("✅ v225: juiste bron bij Search, mislukking en succesvolle toevoeging.")
