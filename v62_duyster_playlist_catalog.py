"""Offline extra Duyster catalogue: user's own Spotify playlist.
No Spotify calls; only reads completed, validated export JSON.
"""
import json
from pathlib import Path

PLAYLIST_ID = '1rsnoOydiRqByY17iQRxUV'
CATALOG_FILE = Path(__file__).with_name('v62_duyster_playlist_catalog.json')


def _norm(s):
    import re, unicodedata
    s = unicodedata.normalize('NFKD', str(s or '')).casefold()
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def catalog(cache=None):
    if not CATALOG_FILE.exists():
        return {}
    data = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
    if data.get('playlist_id') != PLAYLIST_ID or data.get('complete') is not True:
        raise ValueError('Duyster-playlistcatalogus ongeldig/onvolledig; niet gebruiken')
    tracks = data.get('tracks')
    if not isinstance(tracks, list) or len(tracks) != data.get('total'):
        raise ValueError('Duyster-playlistcatalogus heeft verkeerd aantal tracks')
    result = {}
    for tr in tracks:
        if not isinstance(tr, dict):
            continue
        artist, title = tr.get('artist'), tr.get('title')
        if not artist or not title:
            continue
        key = _norm(artist) + '|||' + _norm(title)
        if key.strip('|'):
            result[key] = {'artist': artist, 'title': title, 'uri': tr.get('uri'), 'isrc': tr.get('isrc')}
    return result
