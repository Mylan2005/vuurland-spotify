#!/usr/bin/env python3
"""Read-only Vuurland state health and unmatched catalog report. No Spotify/network."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    except (ValueError, OSError) as e:
        return {'_read_error': str(e)}


def failed_list(cache):
    raw = cache.get('__v51_radio_failed_searches', {})
    result = []
    if isinstance(raw, dict):
        for key, n in raw.items():
            if not isinstance(key, str):
                continue
            try:
                count = int(n)
            except (ValueError, TypeError):
                continue
            if count > 0:
                result.append((count, key))
    return sorted(result, key=lambda x: (-x[0], x[1].casefold()))


def make_report(folder):
    cache = read_json(folder / '.vuurland_spotify_cache.json')
    queue = read_json(folder / 'vuurland_live_queue.json')
    seen = read_json(folder / 'vuurland_seen.json')
    lines = ['# Vuurland — dagelijks gezondheidsrapport', '',
             f'Gemaakt (UTC): {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}', '',
             'Dit rapport leest alleen bestaande GitHub-state. Geen Spotify-aanvragen, geen mutaties.', '']
    warnings = []
    for label, name, data in [('Cache', '.vuurland_spotify_cache.json', cache),
                              ('Wachtrij', 'vuurland_live_queue.json', queue),
                              ('Geziene nummers', 'vuurland_seen.json', seen)]:
        if data is None:
            warnings.append(f'{name} ontbreekt')
            lines.append(f'- {label}: ontbreekt (geen conclusie over live status)')
        elif isinstance(data, dict) and '_read_error' in data:
            warnings.append(f'{name} is niet leesbaar')
            lines.append(f'- {label}: niet leesbaar')
        elif label == 'Wachtrij':
            lines.append(f'- Wachtrij: {len(data)} items' if isinstance(data, list) else '- Wachtrij: onbekend formaat')
        else:
            lines.append(f'- {label}: aanwezig ({len(data)} bovenliggende velden)' if isinstance(data, (dict, list)) else f'- {label}: onverwacht formaat')
    if isinstance(cache, dict) and '_read_error' not in cache:
        failures = failed_list(cache)
        lines.extend(['', f'## Moeilijke catalogusmatches ({len(failures)})', '',
                      'Dit zijn historische mislukte zoekacties, geen bewijs dat nummers ontbreken op Spotify.',
                      'Automatisch toevoegen blijft verboden zonder de bestaande volledige matchcontrole.', ''])
        if failures:
            for n, key in failures[:100]:
                clean_key = re.sub(r'[\r\n`]+', ' ', key)[:180]
                lines.append(f'- {n} pogingen — `{clean_key}`')
        else:
            lines.append('Geen geregistreerde mislukte zoekacties.')
    lines.extend(['', '## Zelfherstel en controle', '',
                  '- 429/403/5xx-pauzes en status-push-herstel: geregeld door bestaande sync.',
                  '- Nieuwe code: v86-tests moeten slagen vóór een volgende Spotify-ronde.',
                  '- Dit is geen bewijs van huidige Spotify-beschikbaarheid of een volledige audit van de playlist.'])
    if warnings:
        lines.extend(['', '## Aandachtspunten', ''] + [f'- {w}' for w in warnings])
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    report = make_report(a.data_dir)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(report, encoding='utf-8')
        print('Rapport geschreven:', a.output)
    else:
        print(report)


if __name__ == '__main__':
    main()
