"""Offline regression: visible search attempts for every radio source, no Spotify calls."""
import io
import tempfile
from pathlib import Path
from live_music_stream import stream

radio = (
    ("radio_x_chilled", "Oasis - The Masterplan"),
    ("dreampop_radio", "Big Deal - Catch Up"),
    ("indie_select", "A Projection - Young Days"),
    ("dkfm_edge", "Fern Murphy - Why Never Here"),
    ("dark_edge", "Portishead - Only You"),
    ("dkfm_shoegaze", "Tiny Fireflies - Nothing"),
    ("dkfm_classic", "Veldt - End All To Be All"),
    ("duyster", "Honeyglaze - Burglar"),
)
lines=[]
for source, song in radio:
    lines += [f"🔢 v221 bronrotatie: FIFO-volgnummer 100 geselecteerd (bron: {source}).",
              f"🔎 Spotify zoeken: {song}",
              f"🎯 v224 Spotify-zoekbeurt: {source}"]
    if source in ("dkfm_edge", "duyster"):
        lines += [f"🎯 v224 Spotify-toevoegbeurt: {source}",
                  f"✅ Toegevoegd: {song}"]
    else:
        lines += [f"⚠️ Geen betrouwbare Spotify-match gevonden: {song}"]
with tempfile.TemporaryDirectory() as folder:
    output=[]
    log=Path(folder)/"technical.log"
    stream(io.StringIO("\n".join(lines)+"\n"), log, emit=lambda line, **kwargs: output.append(line))
    assert log.read_text(encoding="utf-8").count("🎯 v224 Spotify-zoekbeurt:") == 8
    for source, song in radio:
        mapping = {"dreampop_radio":"Dreampop Radio",
                   "dkfm_classic":"DKFM Classic",
                   "indie_select":"Indie Select",
                   "dkfm_edge":"DKFM Edge",
                   "duyster":"Duyster archief"}
        label=mapping.get(source)
        if label:
            assert any(f"| {label} | Spotify-zoekbeurt: {song}" in line for line in output), (source, output)
        if source in ("dkfm_edge", "duyster"):
            assert any("✅ " in line and f"| {label} |" in line for line in output)
        else:
            assert any("⚠️ " in line and ("Geen betrouwbare Spotify-match: " + song) in line for line in output)
    assert len([line for line in output if line.startswith("🔎 ")]) == 8
    assert len([line for line in output if line.startswith("⚠️ ")]) == 6
    assert len([line for line in output if line.startswith("✅ ")]) == 2
print("✅ v226: alle zoekbeurten zichtbaar, ook als Spotify niets betrouwbaar vindt.")
