"""Regressies voor bronvermelding na v221-rotatie en toelating Eefje."""
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from live_music_stream import stream
from maak_muziekoverzicht import extract
from vuurland_music_policy import global_music_reject_reason

lines = [
    "📻 Vuurland sync\n",
    "Wed Nov 11 19:13:00 UTC 2026\n",
    "🔢 v221 bronrotatie: FIFO-volgnummer 12001 geselecteerd (bron: vuurland).\n",
    "✅ Toegevoegd: EEFJE DE VISSER - Onomkeerbaar\n",
    "🔢 v221 bronrotatie: FIFO-volgnummer 12002 geselecteerd (bron: dkfm_shoegaze).\n",
    "✅ Toegevoegd: Ziggy Marley - Drive\n",
    "🔢 v120 gezamenlijke FIFO: volgnummer 12003 geselecteerd (bron: duyster).\n",
    "✅ Toegevoegd: Other Artist - Another Title\n",
]
with TemporaryDirectory() as directory:
    result = []
    stream(iter(lines), Path(directory) / "technical.log", emit=lambda value, **_: result.append(value))
assert len(result) == 3
assert "Studio Brussel Vuurland" in result[0] and "Bron onbekend" not in result[0]
assert "DKFM Shoegaze Radio" in result[1] and "Bron onbekend" not in result[1]
assert "Duyster archief" in result[2] and "Bron onbekend" not in result[2]

rows = extract(lines)
assert len(rows) == 3, rows
assert [row[1] for row in rows] == [
    "Studio Brussel Vuurland", "DKFM Shoegaze Radio", "Duyster archief"
]
assert [row[4] for row in rows] == ["12001", "12002", "12003"]
excluded = json.loads(Path(__file__).with_name("vuurland_user_exclusions.json").read_text(encoding="utf-8"))
assert ["eefje de visser", "onomkeerbaar"] not in excluded["pairs"]
assert global_music_reject_reason("Eefje de Visser", "Onomkeerbaar") is None
assert global_music_reject_reason("Ziggy Marley", "Drive") is None
assert ["m.i.a.", "paper planes"] in excluded["pairs"]
print("✅ Oude en nieuwe logregels tonen bron; Eefje en Ziggy blijven toegelaten.")
