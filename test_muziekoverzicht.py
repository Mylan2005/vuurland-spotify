from pathlib import Path
from tempfile import TemporaryDirectory
from maak_muziekoverzicht import extract,write_report
sample='''========================================
📻 Vuurland sync
Sun Oct 25 11:02:57 UTC 2026
🔢 v120 gezamenlijke FIFO: volgnummer 604 geselecteerd (bron: indie_select).
🔎 Spotify zoeken: Hot Chip - Need You Now
✅ Toegevoegd: Hot Chip - Need You Now
🔢 v120 gezamenlijke FIFO: volgnummer 605 geselecteerd (bron: dkfm_edge).
⚠️ Geen betrouwbare Spotify-match gevonden
🔢 v120 gezamenlijke FIFO: volgnummer 606 geselecteerd (bron: dark_edge).
✅ Toegevoegd: Editors - Cold
'''
rows=extract(sample.splitlines())
assert len(rows)==2,rows
assert rows[0][1:4]==('Indie Select','Hot Chip','Need You Now'),rows
assert rows[1][1]=='Dark Edge Radio',rows
assert rows[0][0]=='25/10/2026 12:02',rows
with TemporaryDirectory() as d:
    path=Path(d)
    (path/'log').write_text(sample,encoding='utf-8')
    write_report(path/'log',path/'out.md',path/'out.txt')
    assert 'Indie Select' in (path/'out.md').read_text()
    assert 'Geen betrouwbare' not in (path/'out.txt').read_text()
    assert len(extract([]))==0
print('✅ Offline tests: alleen succesregels, juiste bron, Belgische tijd en lege log.')
