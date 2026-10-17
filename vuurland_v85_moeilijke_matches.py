"""Offline read-only failure diagnosis; never modifies cache, playlist or Spotify."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description='Vuurland v85 moeilijke tracks: offline overzicht')
parser.add_argument('--data-dir', default='.', help='Map met .vuurland_spotify_cache.json')
args = parser.parse_args()
cache_path = Path(args.data_dir) / '.vuurland_spotify_cache.json'
with cache_path.open(encoding='utf-8') as f:
    cache = json.load(f)
if not isinstance(cache, dict):
    raise SystemExit('Cache is geen JSON-object; niets aangepast')
failed = cache.get('__v51_radio_failed_searches', {}) or {}
entries = cache.get('__v47_failed_tracks', {}) or {}
keys = set(cache.get('__playlist_keys', []) or [])
confirmed = cache.get('__v82_confirmed_catalog', {}) or {}
if not all(isinstance(x, dict) for x in (failed, entries, confirmed)):
    raise SystemExit('Onbekende cachestructuur; niets aangepast')
print('🔥 v85 — moeilijke Spotify-matches (alleen lezen)')
print('Geen Spotify-requests; geen bestanden gewijzigd.\n')
for key, count in sorted(failed.items(), key=lambda x: (-int(x[1] or 0), x[0])):
    entry = entries.get(key) or {}
    name = f"{entry.get('artist', key.split('|||')[0])} — {entry.get('title', key.split('|||')[-1])}"
    if key in keys:
        status = 'AL IN PLAYLIST-CACHE; oude fout mogelijk'
    elif key in confirmed:
        status = 'BEVESTIGDE CATALOGUSLOCATOR; opnieuw valideren'
    else:
        status = 'HANDMATIG CATALOGUS ONDERZOEK NODIG'
    print(f'{int(count or 0):2d} pogingen | {name} | {status}')
print('\nℹ️ Zoek geen extra Spotify-nummers automatisch; bevestig catalogus-ID eerst.')
