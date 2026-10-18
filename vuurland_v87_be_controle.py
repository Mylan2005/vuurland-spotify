#!/usr/bin/env python3
"""Manuele read-only Spotify BE catalogusaudit, los van de Vuurland sync."""
import json, os, re, time, unicodedata
from pathlib import Path
import requests

TRACKS = [
 ('B-Tribe', 'Overture (Concierto de Aranjuez)', None),
 ('Clear Season', "Don't Take Too Long", None),
 ('Cowboy Junkies', 'Black Eyed Man', None),
 ('Eric Burdon & War', 'Summer', None),
 ('Ludwig van Beethoven', 'Für Elise', None),
 ('Pinback', 'Loro', None),
 ('Rickie Lee Jones', 'Little Mysteries', None),
 ('Sarah Harmer', 'Lodestar', None),
 ('Colin Hay', 'Hold On To My Hand', None),
 ('Largo', 'Hand in Mine', None),
 ('Nick Drake', 'Hangin On A Star', '3lpkLZfD2RJltSaAGgmoxb'),
 ('Nick Drake', 'Hazey Jane', None),
 ('Bon Iver', '22 (OVER S∞∞N)', None),
 ('Nick Lowe', 'When I Write The Book', None),
 ('Pieta Brown', 'Lullaby', None),
 ('Raymond Kāne', 'Popoki Slack Key', None),
 ('The Christian Club feat. Lucy Ryan', 'Atlas', None),
 ('This Is Lorelei', 'Box for Buddy, Box for Star', None),
]


def normalize(t):
    t = unicodedata.normalize('NFKD', str(t).casefold())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'∞+', 'oo', t)
    t = re.sub(r'(?<=[a-z])\?\?(?=[a-z])', 'oo', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def summarize(item):
    if not item:
        return None
    return {'name': item.get('name'),
            'artists': [x.get('name') for x in item.get('artists', [])],
            'id': item.get('id'), 'uri': item.get('uri'),
            'is_playable': item.get('is_playable'),
            'restrictions': item.get('restrictions'),
            'external_urls': item.get('external_urls'),
            'isrc': (item.get('external_ids') or {}).get('isrc')}


def token():
    cid, refresh = os.getenv('SPOTIFY_CLIENT_ID'), os.getenv('SPOTIFY_REFRESH_TOKEN')
    if not cid or not refresh:
        raise SystemExit('Spotify-secrets ontbreken. Geen requests uitgevoerd.')
    response = requests.post('https://accounts.spotify.com/api/token',
       data={'grant_type':'refresh_token','client_id':cid,'refresh_token':refresh}, timeout=25)
    response.raise_for_status()
    return response.json()['access_token']


def get(session, bearer, url, params):
    response = session.get(url, headers={'Authorization':f'Bearer {bearer}'},params=params,timeout=25)
    if response.status_code == 429:
        raise RuntimeError('Spotify 429: audit gestopt, geen automatische retry.')
    response.raise_for_status()
    return response.json()


def main():
    bearer = token()
    session = requests.Session()
    results = []
    for index, (artist, title, direct_id) in enumerate(TRACKS, 1):
        row = {'number': index, 'requested_artist': artist, 'requested_title': title,
               'market': 'BE', 'status': 'handmatige controle nodig', 'candidates': []}
        # Eén gerichte GET per titel, geen brede/automatische acceptatie.
        try:
            query = f'{artist} {title}'
            data = get(session, bearer, 'https://api.spotify.com/v1/search',
                       {'q':query,'type':'track','market':'BE','limit':10})
            row['candidates'] = [summarize(x) for x in data.get('tracks',{}).get('items', [])]
            if direct_id:
                detail = get(session, bearer, f'https://api.spotify.com/v1/tracks/{direct_id}', {'market':'BE'})
                row['direct_user_link'] = summarize(detail)
            # No automatische goedkeuring: zoekhits en get-track zonder expliciete
            # is_playable=true bevestigen Belgische speelbaarheid niet altijd.
            row['status'] = 'resultaten ontvangen; niet automatisch toevoegen'
        except Exception as e:
            row['status'] = f'audit onderbroken: {type(e).__name__}: {str(e)[:140]}'
            results.append(row)
            break
        results.append(row)
        print(f'{index:02d}/18 onderzocht: {artist} — {title}; {len(row["candidates"])} kandidaten')
        time.sleep(0.5)
    Path('vuurland_v87_be_resultaten.json').write_text(json.dumps(results,ensure_ascii=False,indent=2), encoding='utf-8')
    rows = ['# Vuurland v87 — Spotify BE cataloguscontrole', '',
            '**Alleen-lezen:** geen nummers toegevoegd, geen cache of wachtrij gewijzigd.',
            'Spotify Search geeft kandidaten; gebruikersafspeelbaarheid blijft zo nodig handmatig te verifiëren.', '',
            '| # | RadioBox-nummer | Spotify-kandidaten | Status |', '|---|---|---:|---|']
    for row in results:
        rows.append(f'| {row["number"]} | {row["requested_artist"]} — {row["requested_title"]} | {len(row["candidates"])} | {row["status"]} |')
    Path('vuurland_v87_be_rapport.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    if len(results) != len(TRACKS) or any(r['status'].startswith('audit onderbroken') for r in results):
        raise SystemExit('Audit onvolledig; bekijk rapport. Spotify-sync blijft onaangeroerd.')

if __name__ == '__main__':
    main()
