#!/usr/bin/env python3
"""Alleen-lezen rapport uit bestaande GitHub Actions-sync-log; geen Spotify-aanroepen."""
import argparse
import pathlib
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SOURCE_NAMES = {
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
SELECT = re.compile(r'^🔢 v120 gezamenlijke FIFO: volgnummer\s+(\d+)\s+geselecteerd\s+\(bron:\s*([a-z0-9_]+)\)')
ADDED = re.compile(r'^✅ Toegevoegd:\s*(.+?)\s+-\s+(.+?)\s*$')
RUN_DATE = re.compile(r'^[A-Z][a-z]{2} [A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d\s+(?:UTC|GMT)\s+\d{4}$')

def extract(lines):
    rows=[]
    selected=None
    expect_date=False
    clock='tijd onbekend'
    for line in lines:
        line=line.strip()
        if line == '📻 Vuurland sync':
            expect_date=True
            selected=None
            continue
        if expect_date and RUN_DATE.match(line):
            expect_date=False
            try:
                utc=datetime.strptime(line, '%a %b %d %H:%M:%S %Z %Y').replace(tzinfo=timezone.utc)
                clock=utc.astimezone(ZoneInfo('Europe/Brussels')).strftime('%d/%m/%Y %H:%M')
            except ValueError:
                clock=line
            continue
        m=SELECT.match(line)
        if m:
            selected=(m.group(1), m.group(2))
            continue
        m=ADDED.match(line)
        if m:
            number, sid=selected if selected else ('?', 'onbekend')
            rows.append((clock, SOURCE_NAMES.get(sid, sid), m.group(1), m.group(2), number))
            selected=None
    return rows

def write_report(log, md, txt):
    lines=pathlib.Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if pathlib.Path(log).exists() else []
    records=extract(lines)
    header=f'Vuurland → Spotify | {len(records)} succesvol toegevoegd nummer(s) in deze workflow-uitvoering'
    text=[header, 'Tijdzone: België (Europe/Brussels)', '']
    markdown=['# 🎵 Vuurland — toegevoegde nummers', '', f'**{len(records)} succesvol toegevoegd** in deze workflow-uitvoering.', '', 'Tijdzone: België (Europe/Brussels). Dit is een overzicht, niet de technische log.', '']
    if records:
        markdown.extend(['| Tijdstip | Radiobron | Artiest — titel | FIFO |', '|---|---|---|---|'])
        for stamp, source, artist, title, number in records:
            text.append(f'✅ {stamp} | {source} | {artist} — {title} | FIFO #{number}')
            escape=lambda s:str(s).replace('|', '\\|').replace('\n',' ')
            markdown.append(f'| {escape(stamp)} | {escape(source)} | {escape(artist)} — {escape(title)} | {escape(number)} |')
    else:
        text.append('Geen succesvolle toevoegingen gevonden in de beschikbare log.')
        markdown.append('Geen succesvolle toevoegingen gevonden in de beschikbare log.')
    pathlib.Path(md).write_text('\n'.join(markdown)+'\n', encoding='utf-8')
    pathlib.Path(txt).write_text('\n'.join(text)+'\n', encoding='utf-8')
    return records

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('log', nargs='?', default='vuurland_matcher_sync.log')
    p.add_argument('--md', default='vuurland_toegevoegde_nummers.md')
    p.add_argument('--txt', default='vuurland_toegevoegde_nummers.txt')
    a=p.parse_args()
    records=write_report(a.log, a.md, a.txt)
    print(f'🎵 Muziekoverzicht gemaakt: {len(records)} succesvolle toevoeging(en).')
