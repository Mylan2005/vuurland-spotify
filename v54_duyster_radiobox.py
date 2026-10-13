"""v54: Duyster only completes artists explicitly discovered via the two RadioBox sources.
No Spotify network calls are made here. The existing sync owns matching, dedupe, saves and throttling.
"""
import random
import re
import time
import unicodedata
import duyster_bron


def norm(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def radio_artists(cache):
    result = set()
    discovered = cache.get('__v47_radio_discovered', {})
    for source in ('vuurland', 'mellow_mix'):
        for entry in discovered.get(source, []):
            if '|||' in entry:
                artist = entry.split('|||', 1)[0]
                # Do not infer a guest artist from a track's artist field.
                if norm(artist):
                    result.add(norm(artist))
    return result


def prepare(cache, live_queue, seen, normalize_match):
    # Ensure previous Duyster retry attempts cannot spontaneously reintroduce unrelated artists.
    # Tijdens volledige v55-heropbouw eerst alle historische RadioBox-tracks verwerken.
    if cache.get('__v55_radio_rebuild_pending'):
        radio_pending = sum(1 for x in live_queue if isinstance(x, dict) and x.get('source') in ('vuurland', 'mellow_mix'))
        if radio_pending:
            print(f'📻 v55: RadioBox-heropbouw eerst ({radio_pending} in wachtrij); Duyster wacht')
            return
        cache['__v55_radio_rebuild_pending'] = False
        print('✅ v55: RadioBox-wachtrij afgewerkt; Duyster-aanvullingen kunnen starten')
    eligible_artists = radio_artists(cache)
    before = len(live_queue)
    live_queue[:] = [x for x in live_queue if not (
        isinstance(x, dict) and x.get('source') == 'duyster'
        and norm(x.get('artist', '')) not in eligible_artists
    )]
    if len(live_queue) != before:
        print(f'🛡️ v54: {before - len(live_queue)} oude Duyster-wachtrijitems zonder RadioBox-artiest verwijderd')
    if not eligible_artists:
        print('🌙 v54: nog geen uit RadioBox bevestigde artiesten; geen Duyster-selectie')
        return
    duyster_bron.check_new_episode(cache)
    catalog = duyster_bron._songs(cache)
    pending = {(normalize_match(x.get('artist', '')), normalize_match(x.get('title', '')))
               for x in live_queue if isinstance(x, dict)}
    issued = cache.setdefault('__v54_duyster_radio_issued', {})
    failed = set(cache.get('__v50_duyster_unmatched', {}))
    now = int(time.time())
    choices = []
    for song in catalog.values():
        a, t = song['artist'], song['title']
        if norm(a) not in eligible_artists:
            continue
        key = normalize_match(a) + '|||' + normalize_match(t)
        if key in failed or key in seen or (normalize_match(a), normalize_match(t)) in pending:
            continue
        # On restart avoid duplicating work before the normal seen/retry machinery finishes.
        if now - int(issued.get(key, 0)) < 86400:
            continue
        choices.append(song)
    if not choices:
        print(f'🌙 v54: geen ontbrekende verwerkbare archiefkandidaten bij {len(eligible_artists)} RadioBox-artiesten')
        return
    active_duyster = sum(1 for x in live_queue if isinstance(x, dict) and x.get('source') == 'duyster')
    if active_duyster >= 3:
        return
    song = random.SystemRandom().choice(choices)
    key = normalize_match(song['artist']) + '|||' + normalize_match(song['title'])
    live_queue.append({'artist': song['artist'], 'title': song['title'], 'source': 'duyster'})
    issued[key] = now
    print(f'🌙 v54 RadioBox-artiest aanvullen: {song["artist"]} — {song["title"]} ({len(choices)} kandidaten)')
