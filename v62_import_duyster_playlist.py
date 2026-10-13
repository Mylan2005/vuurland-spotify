#!/usr/bin/env python3
"""Read-only complete Spotify playlist export. Never overwrites on partial scan.
Must run only after Spotify cooldown, with env vars SPOTIFY_CLIENT_ID and SPOTIFY_REFRESH_TOKEN.
"""
import datetime, json, os, pathlib, sys, time
import requests

PLAYLIST_ID = '1rsnoOydiRqByY17iQRxUV'
OUT = pathlib.Path(__file__).with_name('v62_duyster_playlist_catalog.json')


def fail_429(response):
    if response.status_code == 429:
        raise RuntimeError('Spotify 429; Retry-After: ' + response.headers.get('Retry-After', 'onbekend') + '. Geen retry.')


def run():
    client_id = os.environ['SPOTIFY_CLIENT_ID']
    refresh = os.environ['SPOTIFY_REFRESH_TOKEN']
    token_resp = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'refresh_token', 'refresh_token': refresh, 'client_id': client_id,
    }, timeout=35)
    fail_429(token_resp)
    token_resp.raise_for_status()
    token = token_resp.json()['access_token']
    session = requests.Session()
    result = []
    offset, total = 0, None
    while True:
        resp = session.get(
            f'https://api.spotify.com/v1/playlists/{PLAYLIST_ID}/items',
            headers={'Authorization': 'Bearer ' + token},
            params={'limit': 100, 'offset': offset}, timeout=35,
        )
        fail_429(resp)
        resp.raise_for_status()
        page = resp.json()
        items, n = page.get('items'), page.get('total')
        if not isinstance(items, list) or not isinstance(n, int):
            raise RuntimeError('Spotify antwoord heeft ongeldige pagina')
        if total is None:
            total = n
        if total != n:
            raise RuntimeError('Playlist gewijzigd tijdens import; probeer later opnieuw')
        for item in items:
            track = item.get('item') or item.get('track') or {}
            if not isinstance(track, dict) or not str(track.get('uri', '')).startswith('spotify:track:'):
                raise RuntimeError('Niet-ondersteund playlistitem; import gestopt')
            artists = track.get('artists') or []
            artist = (artists[0] or {}).get('name', '') if artists else ''
            result.append({'artist': artist, 'title': track.get('name', ''),
                           'uri': track['uri'], 'isrc': (track.get('external_ids') or {}).get('isrc')})
        offset += len(items)
        print(f'📚 Duyster eigen playlist: {offset}/{total} gelezen')
        if not page.get('next'):
            if offset != total:
                raise RuntimeError(f'Onvolledige import {offset}/{total}')
            break
        if not items or offset > 100000:
            raise RuntimeError('Paginering vastgelopen')
        time.sleep(0.5)
    payload = {'playlist_id': PLAYLIST_ID, 'complete': True, 'total': total,
               'scanned_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'tracks': result}
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(OUT)
    print(f'✅ Volledige Duyster-catalogus: {total} nummers → {OUT}')


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('STOP: ' + str(exc)); sys.exit(1)
