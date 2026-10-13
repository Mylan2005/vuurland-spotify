#!/usr/bin/env python3
"""Make a non-authoritative report from existing Vuurland sync logs. No Spotify calls."""
import argparse
import csv
import json
import pathlib
import re
from datetime import datetime, timezone

SEARCH = re.compile(r'Spotify zoeken:\s*(.+?)\s+-\s+(.+)$')
UNMATCHED = re.compile(r'Geen betrouwbare Spotify-match gevonden:\s*(.+?)\s+-\s+(.+)$')
PARKED = re.compile(r'Radio:\s*(.+?)\s+-\s+(.+?)\s+na\s+\d+\s+mislukte zoekacties geparkeerd')
QUERY = 'Spotify-query zonder veilige match:'
REJECTED = 'Spotify top-kandidaten afgewezen:'
FIELDS = ['bron', 'artiest', 'titel', 'status', 'laatste_spotify_query', 'afgewezen_kandidaten', 'mislukte_zoekacties_in_log', 'opmerking']

def make_report(log_path, out_dir):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = {}
    current = None
    if pathlib.Path(log_path).exists():
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                m = SEARCH.search(line)
                if m:
                    current = (m.group(1).strip(), m.group(2).strip())
                    continue
                if QUERY in line and current:
                    entry = events.setdefault(current, {'query':'', 'candidates':'', 'status':'Onzekere match', 'attempts':0})
                    entry['query'] = line.split(QUERY, 1)[1].strip()
                    continue
                if REJECTED in line and current:
                    entry = events.setdefault(current, {'query':'', 'candidates':'', 'status':'Onzekere match', 'attempts':0})
                    entry['candidates'] = line.split(REJECTED, 1)[1].strip()
                    continue
                m = UNMATCHED.search(line)
                if m:
                    key = (m.group(1).strip(), m.group(2).strip())
                    entry = events.setdefault(key, {'query':'', 'candidates':'', 'status':'Onzekere match', 'attempts':0})
                    entry['attempts'] += 1
                    entry['status'] = 'Geen betrouwbare Spotify-match'
                    current = key
                    continue
                m = PARKED.search(line)
                if m:
                    key = (m.group(1).strip(), m.group(2).strip())
                    entry = events.setdefault(key, {'query':'', 'candidates':'', 'status':'Onzekere match', 'attempts':0})
                    entry['status'] = 'Geparkeerd na mislukte zoekacties'
    records = []
    for (artist,title), e in sorted(events.items(), key=lambda t:(t[0][0].casefold(),t[0][1].casefold())):
        records.append({'bron':'Niet afzonderlijk gelogd', 'artiest':artist, 'titel':title,
                        'status':e['status'], 'laatste_spotify_query':e['query'],
                        'afgewezen_kandidaten':e['candidates'],
                        'mislukte_zoekacties_in_log':e['attempts'],
                        'opmerking':'Kandidaten uit GitHub-runlog; controleer handmatig, geen automatische goedkeuring.'})
    with (out_dir/'vuurland_matcher_rapport.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader();writer.writerows(records)
    (out_dir/'vuurland_matcher_rapport.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Alle sync-rondes in deze GitHub Actions-run; niet eerdere runs',
        'spotify_requests':0,'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'📄 Matcher-rapport: {len(records)} unieke onzekere/afgewezen matches uit deze GitHub-run.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('log',nargs='?',default='vuurland_matcher_sync.log')
    p.add_argument('--output-dir',default='v64_matcher_rapport');args=p.parse_args()
    make_report(args.log,args.output_dir)
