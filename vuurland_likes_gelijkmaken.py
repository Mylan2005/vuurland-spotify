#!/usr/bin/env python3
"""One-time safe Spotify likes alignment. Only deletes 12 snapshot-verified extras."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

PLAYLIST = '555lFTvdRswe9ukybmOM8T'
EXTRA = {
 '080EAQQYBOlSbutDak6tfi': 'Zach Bryan & Bon Iver — Boys of Faith',
 '0qLerBz0rNYKARVqBTzLLX': 'King Viktor & The Haunted Youth — Riptide',
 '1HMQmOWrkieKYWlFsjUP3D': 'The Paper Kites — Bloom (Bonus Track)',
 '2ppxa6borKGB4WCTVWqFxy': 'Tiny Ruins — Sparklers (Solo)',
 '73SuMNfhwGgEpv1LgLb3C3': 'Explosions in the Sky — Six Days at the Bottom of the Ocean',
 '4sYn64V9gqP6bpkOGw5B9k': 'Explosions in the Sky — Your Hand in Mine',
 '259K0DlR586fupbKcwQNBW': 'Half Moon Run — adore u (Live from the Treehouse)',
 '5EYi2rH4LYs6M21ZLOyQTx': 'Rex Orange County & Benny Sings — Loving Is Easy',
 '5GbVzc6Ex5LYlLJqzRQhuy': 'Sufjan Stevens — Mystery of Love',
 '79hqdNpnWPVVxmZiDfKaIL': 'Hammock — Dark Beyond the Blue',
 '4QhMkNvlwdWcQ8u1Lobbz4': 'alt-J — Happier When You’re Gone',
 '5g8xjUhQ3OwOwIziC6hBtn': 'The Paper Kites & Julia Stone — Without Your Love',
}

def request(url, token=None, method='GET', data=None, form=False):
    h = {'Accept':'application/json'}
    if token: h['Authorization'] = 'Bearer ' + token
    if data is not None: h['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    req = urllib.request.Request(url, data=(urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=50) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        print(f'⛔ Spotify HTTP {e.code} bij {method} {url.split("?")[0]}. Geen verdere wijzigingen.', file=sys.stderr)
        if e.code == 429: print('Spotify rate-limit: wacht tot Retry-After verstreken is.', file=sys.stderr)
        raise SystemExit(2)

def get_pages(url, token, playlist=False):
    ids = []
    while url:
        r = request(url, token)
        for item in r.get('items', []):
            track = item.get('track') if playlist else item
            if track and track.get('type') == 'track' and track.get('id'):
                ids.append(track['id'])
            elif track and track.get('id') and 'type' not in track:
                ids.append(track['id'])
            else:
                print('⛔ Onbekend/ongeldig Spotify-item. Stop voor veiligheid.', file=sys.stderr)
                raise SystemExit(2)
        url = r.get('next')
    return ids

def main():
    cid = os.environ['SPOTIFY_CLIENT_ID']
    rt = os.environ['SPOTIFY_REFRESH_TOKEN']
    token = request('https://accounts.spotify.com/api/token', method='POST', form=True,
                    data={'grant_type':'refresh_token','refresh_token':rt,'client_id':cid})['access_token']
    print('🔎 Lees volledige Vuurland-playlist en Liked Songs opnieuw (alleen-lezen)...', flush=True)
    playlist = get_pages(f'https://api.spotify.com/v1/playlists/{PLAYLIST}/tracks?limit=100', token, True)
    liked = get_pages('https://api.spotify.com/v1/me/tracks?limit=50', token)
    ps, ls = set(playlist), set(liked)
    only_likes, only_playlist = ls - ps, ps - ls
    print(f'🔥 Playlist: {len(playlist)} items / {len(ps)} unieke nummers')
    print(f'❤️ Likes: {len(liked)} items / {len(ls)} unieke nummers')
    print(f'❤️ Enkel geliket: {len(only_likes)} | 🔥 Enkel playlist: {len(only_playlist)}')
    for tid in sorted(only_likes):
        print('  EXTRA LIKE:', EXTRA.get(tid, 'ONBEKEND!'), tid)
    # Abort if ANYTHING differs from the snapshot-proven exact set.
    if only_likes != set(EXTRA) or only_playlist or len(playlist) != len(ps) or len(liked) != len(ls):
        print('🛑 De actuele Spotify-inhoud wijkt af van de 12 verwachte extra likes. NIETS verwijderd.')
        return 0
    if os.environ.get('FIX_MODE') != 'VERWIJDER_12_EXTRA_LIKES':
        print('✅ Controle klaar. DRY RUN: niets verwijderd.')
        return 0
    # Recheck playlist at deletion time to reduce race with active sync.
    refreshed_ps = set(get_pages(f'https://api.spotify.com/v1/playlists/{PLAYLIST}/tracks?limit=100', token, True))
    if refreshed_ps != ps:
        print('🛑 Playlist veranderde tijdens controle. NIETS verwijderd.')
        return 0
    print('🗑️ Verwijder uitsluitend 12 gecontroleerde extra likes...', flush=True)
    request('https://api.spotify.com/v1/me/tracks', token, 'DELETE', data={'ids': sorted(EXTRA)})
    print('✅ Verwijderverzoek voor exact 12 extra likes gelukt. 🔥 Playlist niet gewijzigd.')
    print('ℹ️ Doorlopende sync kan intussen nieuwe nummers toevoegen; aantallen kunnen daardoor verder stijgen.')
    return 0

if __name__ == '__main__': sys.exit(main())
