#!/usr/bin/env python3
"""Eenmalige reset voor de NIEUWE Vuurland-playlist. Geen Spotify-verzoeken."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import time

ROOT = Path(__file__).resolve().parent
OLD_ID = '555lFTvdRswe9ukybmOM8T'
parser = argparse.ArgumentParser()
parser.add_argument('--playlist-id', required=True, help='ID van de nieuwe, zelf aangemaakte Spotify-playlist')
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
pid = args.playlist_id.strip()
if not re.fullmatch(r'[A-Za-z0-9]{22}', pid):
    parser.error('Geen geldig Spotify-playlist-ID (22 letters/cijfers).')
script = ROOT / 'vuurland_sync.py'
s = script.read_text()
expected = f'PLAYLIST_ID = os.environ.get("VUURLAND_PLAYLIST_ID", "{OLD_ID}")'
if expected not in s:
    parser.error('Onverwachte codeversie of reeds ingesteld playlist-ID; niets aangepast.')
paths = [ROOT / n for n in ('.vuurland_spotify_cache.json', 'vuurland_live_queue.json', 'vuurland_seen.json')]
print('Spotify-playlist voor frisse start:', pid)
print('De Spotify-playlist en Liked Songs worden NIET via de API aangepast.')
print('De lokale JSON-state krijgt een back-up en wordt opnieuw opgebouwd. De playlist blijft onaangeroerd.')
if not args.apply:
    print('VOORBEELD: voer opnieuw uit met --apply na stoppen van de actieve GitHub-run.')
    raise SystemExit(0)
backup = ROOT / ('v69_oude_state_backup_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(exist_ok=False)
for p in paths:
    if p.exists():
        shutil.copy2(p, backup / p.name)
cache = {}
if paths[0].exists():
    old = json.loads(paths[0].read_text())
    if not isinstance(old, dict):
        raise SystemExit('Oude cache ongeldig; reset afgebroken')
    for key in ('__spotify_api_blocked_until', '__spotify_search_blocked_until'):
        until = float(old.get(key, 0) or 0)
        if until > time.time():
            cache[key] = until
cache['__v69_radio_only_fresh_start'] = True
cache['__v42_source_turn'] = 'vuurland'
script.write_text(s.replace(expected, f'PLAYLIST_ID = os.environ.get("VUURLAND_PLAYLIST_ID", "{pid}")'))
paths[0].write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n')
paths[1].write_text('[]\n')
paths[2].write_text('[]\n')
print('OK: playlist-ID bevestigd; cache, wachtrij en seen gereset.')
print('Back-up:', backup)
print('LET OP: commit de drie JSON-bestanden + vuurland_sync.py tegelijk, terwijl oude run UIT staat.')
