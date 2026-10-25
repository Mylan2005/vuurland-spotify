#!/usr/bin/env python3
"""Print een compacte, alleen-lezen muzieksamenvatting van één sync-ronde."""
import pathlib
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from maak_muziekoverzicht import extract


def render(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return '⚠️ Geen logbestand voor deze ronde gevonden.'
    rows = extract(p.read_text(encoding='utf-8', errors='replace').splitlines())
    if not rows:
        return '🎵 Geen nummer toegevoegd in deze ronde.'
    lines = []
    for _clock, source, artist, title, _seq in rows:
        stamp = datetime.now(ZoneInfo('Europe/Brussels')).strftime('%H:%M')
        lines.append(f'✅ {stamp} | {source} | {artist} — {title}')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(sys.argv[1] if len(sys.argv) > 1 else 'vuurland_ronde.log'), flush=True)
