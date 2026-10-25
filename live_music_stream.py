#!/usr/bin/env python3
"""Toon alleen bevestigde Spotify-toevoegingen in live Actions-log.

Alle originele uitvoer wordt gelijktijdig opgeslagen voor diagnose.
Deze code verandert nooit Spotify, de FIFO of JSON-state.
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BRONNEN = {
    'vuurland': 'Studio Brussel Vuurland',
    'mellow_mix': 'Radio Paradise Mellow Mix',
    'big_sonic_heaven': 'Big Sonic Heaven Radio',
    'radio_x_chilled': 'Radio X Chilled',
    'indie_select': 'Indie Select',
    'championship_vinyl': 'Championship Vinyl',
    'dark_edge': 'Dark Edge Radio',
    'dreampop_radio': 'Dreampop Radio',
    'radio_indie_alternative': 'Radio Indie Alternative',
    'dkfm_edge': 'DKFM Edge',
    'dkfm_shoegaze': 'DKFM Shoegaze Radio',
}
SELECTIE = re.compile(r'gezamenlijke FIFO:.*?\(bron:\s*([a-z_]+)\)')


def format_music(raw, source, clock=None):
    if not raw.startswith('✅ Toegevoegd: '):
        return None
    song = raw.split('✅ Toegevoegd: ', 1)[1].strip()
    if not song:
        return None
    if ' - ' in song:
        artist, title = song.split(' - ', 1)
        song = f'{artist} — {title}'
    stamp = clock or datetime.now(ZoneInfo('Europe/Brussels')).strftime('%H:%M')
    return f'✅ {stamp} | {BRONNEN.get(source, source or "Bron onbekend")} | {song}'


def stream(instream, logfile, emit=print):
    source = None
    with open(logfile, 'a', encoding='utf-8', buffering=1) as handle:
        for text in instream:
            handle.write(text)
            line = text.strip()
            selected = SELECTIE.search(line)
            if selected:
                source = selected.group(1)
            music = format_music(line, source)
            if music:
                emit(music, flush=True)
                source = None
            elif line.startswith(('🛑', '❌')):
                # Belangrijke foutmeldingen toch live zichtbaar maken.
                emit(line, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default='vuurland_technische_live.log')
    args = parser.parse_args()
    stream(sys.stdin, Path(args.log))


if __name__ == '__main__':
    main()
