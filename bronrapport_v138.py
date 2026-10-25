#!/usr/bin/env python3
"""Read-only runner report: station heartbeat, queue health, and per-source additions."""
import collections, json, pathlib, re, sys

SOURCES = {
 'vuurland':'Studio Brussel Vuurland','mellow_mix':'Radio Paradise Mellow Mix',
 'big_sonic_heaven':'Big Sonic Heaven Radio','radio_x_chilled':'Radio X Chilled',
 'indie_select':'Indie Select','championship_vinyl':'Championship Vinyl',
 'dark_edge':'Dark Edge Radio','dreampop_radio':'Dreampop Radio',
 'radio_indie_alternative':'Radio Indie Alternative','dkfm_edge':'DKFM Edge',
 'dkfm_shoegaze':'DKFM Shoegaze Radio','dkfm_classic':'DKFM Classic'}
SELECT=re.compile(r'gezamenlijke FIFO: volgnummer\s+\d+\s+geselecteerd\s*\(bron:\s*([a-z_]+)\)')
COUNT=re.compile(r'^(.+?):\s+(\d+) nummers gevonden\.')
ADD=re.compile(r'^✅ Toegevoegd:')

def assess(log, queue):
    lines=pathlib.Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if pathlib.Path(log).is_file() else []
    rounds=0; seen=collections.Counter(); ok=collections.Counter(); added=collections.Counter(); selected=None
    for line in lines:
        line=line.strip()
        if '📻 Vuurland sync' in line: rounds+=1; selected=None
        if line.startswith('📻 ') and line.endswith(' wordt gecontroleerd...'):
            seen[line[2:-len(' wordt gecontroleerd...')]]+=1
        m=COUNT.match(line)
        if m: ok[m.group(1)]+=1
        m=SELECT.search(line)
        if m: selected=m.group(1)
        if ADD.match(line):
            added[selected or 'onbekend']+=1
            selected=None
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
        '| Radiobron | Controle gestart | Titels gevonden (rondes) | Spotify toegevoegd | Nu in queue |',
        '|---|---:|---:|---:|---:|']
    for key,name in SOURCES.items():
        out.append(f'| {name} | {seen[name]} | {ok[name]} | {added[key]} | {counts[key]} |')
    out.extend(['',warning,'',
      '⚠️ Een bron die wel gecontroleerd is maar geen nummers toevoegt, is niet per se defect. '
      'De wachtrij en duplicaatfilter kunnen alle uitzendingen al kennen.',
      '⚠️ Deze rapportage telt regels in het log. Een netwerkfout of ontbrekende log kan een onvolledig beeld geven.',''])
    if rounds >= 3:
        missing=[name for name in SOURCES.values() if ok[name]==0]
        if missing: out.extend(['', '⚠️ Geen succesvolle muzieklijsten bevestigd tijdens deze runner: '+', '.join(missing)])
    pathlib.Path('vuurland_brongezondheid.md').write_text('\n'.join(out),encoding='utf-8')
    print('📊 Brongezondheid opgesteld (alleen-lezen).')
    return rounds,seen,ok,added,counts

if __name__=='__main__':
    assess(*(sys.argv[1:3] or ['vuurland_matcher_sync.log','vuurland_live_queue.json']))
