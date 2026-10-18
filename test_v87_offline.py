"""Veiligheid van de read-only catalogusaudit zonder Spotify-requests."""
import ast
from pathlib import Path
p=Path(__file__).with_name('vuurland_v87_be_controle.py')
s=p.read_text(encoding='utf-8')
ast.parse(s)
assert 'market\':\'BE\'' in s or "'market':'BE'" in s
for forbidden in ('/me/tracks', '/playlists/', 'playlist_add', 'remove_tracks', 'save_cache(', 'save_queue('):
    assert forbidden not in s, f'Write action gevonden: {forbidden}'
ns={'__name__':'v87_test'}
exec(compile(s,str(p),'exec'),ns)
assert len(ns['TRACKS'])==18
assert ns['normalize']('22 (OVER S∞∞N)') == ns['normalize']('22 (over s??n)')
print('✅ v87: 18 tracks, BE-zoekmarkt, geen Spotify-writes, unicode-test')
