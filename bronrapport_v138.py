#!/usr/bin/env python3
"""Read-only runner report: station heartbeat, queue health, and per-source additions."""
import collections, json, pathlib, re, sys

# Must match vuurland_sync.RADIO_SOURCE_ORDER plus the separate Duyster archive.
# This is the full active feed set, not a hand-maintained subset.
ACTIVE_SOURCES = {
 'vuurland':'Studio Brussel Vuurland',
 'mellow_mix':'Radio Paradise Mellow Mix',
 'big_sonic_heaven':'Big Sonic Heaven Radio',
 'radio_x_chilled':'Radio X Chilled',
 'dreampop_radio':'Dreampop Radio',
 'indie_select':'Indie Select',
 'dkfm_edge':'DKFM Edge',
 'dark_edge':'Dark Edge Radio',
 'dkfm_shoegaze':'DKFM Shoegaze Radio',
 'dkfm_classic':'DKFM Classic',
 'egofm_rnb':'egoFM R&B',
 'egofm_chillout':'egoFM Chillout',
 'dj_neihtul':'DJ Neihtul',
 'gri_balkon':'Gri Balkon',
 'ignoreradio_shoegaze':'Ignoreradio Shoegaze',
 'radio_britannia':'Radio Britannia',
 'wbru':'WBRU',
}
# Duyster is a separate archive workflow, not a live RadioBox feed.
ARCHIVE_SOURCES = {
 'duyster':'Duyster archief (aparte workflow)',
}
# Retain old queue labels for visibility, but never present them as active feeds.
LEGACY_SOURCES = {
 'radio_x_main':'Radio X (uitgeschakeld)',
 'championship_vinyl':'Championship Vinyl (historische wachtrij)',
 'radio_indie_alternative':'Radio Indie Alternative (historische wachtrij)',
}
SOURCES = {**ACTIVE_SOURCES, **ARCHIVE_SOURCES, **LEGACY_SOURCES}
SELECT=re.compile(r'(?:gezamenlijke FIFO|v221 bronrotatie): (?:FIFO-)?volgnummer\s+\d+\s+geselecteerd\s*\(bron:\s*([a-z_]+)\)')
SEARCH=re.compile(r'v224 Spotify-zoekbeurt:\s*([a-z_]+)')
ADD_SOURCE=re.compile(r'v224 Spotify-toevoegbeurt:\s*([a-z_]+)')
NO_MATCH=re.compile(r'Geen betrouwbare Spotify-match gevonden:')
COUNT=re.compile(r'^(.+?):\s+(\d+) nummers gevonden\.')
ADD=re.compile(r'^✅ Toegevoegd:')

def assess(log, queue):
    lines=pathlib.Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if pathlib.Path(log).is_file() else []
    rounds=0; seen=collections.Counter(); ok=collections.Counter(); added=collections.Counter()
    searched=collections.Counter(); misses=collections.Counter(); selected=None; search_source=None; add_source=None
    for line in lines:
        line=line.strip()
        if '📻 Vuurland sync' in line:
            rounds+=1; selected=None; search_source=None; add_source=None
        if line.startswith('📻 ') and line.endswith(' wordt gecontroleerd...'):
            seen[line[2:-len(' wordt gecontroleerd...')]]+=1
        m=COUNT.match(line)
        if m: ok[m.group(1)]+=1
        m=SELECT.search(line)
        if m: selected=m.group(1)
        match=SEARCH.search(line)
        if match:
            search_source=match.group(1)
            searched[search_source]+=1
        if NO_MATCH.search(line):
            misses[search_source or selected or 'onbekend']+=1
            search_source=None
        match=ADD_SOURCE.search(line)
        if match: add_source=match.group(1)
        if ADD.match(line):
            added[add_source or selected or 'onbekend']+=1
            selected=None; add_source=None; search_source=None
    try:
        entries=json.loads(pathlib.Path(queue).read_text(encoding='utf-8'))
        if not isinstance(entries,list): raise ValueError('queue is not an array')
        counts=collections.Counter(x.get('source','onbekend') for x in entries if isinstance(x,dict))
        seq=[x.get('_v116_fifo_seq') for x in entries if isinstance(x,dict)]
        invalid=sum(not isinstance(s,int) or isinstance(s,bool) for s in seq)
        duplicate=len(seq)-len(set(str(s) for s in seq))
        warning=f'⚠️ FIFO-data: {invalid} ontbrekende/ongeldige en {duplicate} dubbele volgnummers' if invalid or duplicate else '✅ FIFO-volgnummers uniek en aanwezig'
    except (OSError,ValueError,TypeError) as exc:
        entries=[];counts=collections.Counter();warning=f'⚠️ Wachtrij kon niet gelezen worden: {exc}'
    out=['# 📻 Vuurland — gezondheid per bron','',
        f'**{rounds} syncronde(s) in deze runner** — dit is géén 24-uursstatistiek.','',
        '| Radiobron | Status | Controle gestart | Titels gevonden (rondes) | Spotify Search | Geen match | Spotify toegevoegd | Nu in queue |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for key,name in SOURCES.items():
        if key in ACTIVE_SOURCES:
            status = 'Actief'
        elif key in ARCHIVE_SOURCES:
            status = 'Archief (aparte workflow)'
        else:
            status = 'Historisch/uitgeschakeld'
        out.append(f'| {name} | {status} | {seen[name]} | {ok[name]} | {searched[key]} | {misses[key]} | {added[key]} | {counts[key]} |')
    out.extend(['',warning,'',
      '⚠️ Spotify Search telt echte zoekbeurten, niet geslaagde nummers. Bij een volle wachtrij zonder zoekbeurten moet de bronselectie onderzocht worden. ',
      '⚠️ Een bron die wel gecontroleerd is maar geen nummers toevoegt, is niet per se defect. '
      'De wachtrij en duplicaatfilter kunnen alle uitzendingen al kennen.',
      '⚠️ Deze rapportage telt regels in het log. Een netwerkfout of ontbrekende log kan een onvolledig beeld geven.',''])
    if rounds >= 3:
        missing=[name for name in ACTIVE_SOURCES.values() if ok[name]==0]
        if missing: out.extend(['', '⚠️ Geen succesvolle muzieklijsten bevestigd tijdens deze runner: '+', '.join(missing)])
    pathlib.Path('vuurland_brongezondheid.md').write_text('\n'.join(out),encoding='utf-8')
    print('📊 Brongezondheid opgesteld (alleen-lezen).')
    return rounds,seen,ok,added,counts

if __name__=='__main__':
    assess(*(sys.argv[1:3] or ['vuurland_matcher_sync.log','vuurland_live_queue.json']))
