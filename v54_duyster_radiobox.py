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


def playlist_artists(cache):
    """Artiesten van tracks die volgens de recente playlist-snapshot echt in 🔥 staan.

    Alleen de volledige playlist wordt gebruikt, NIET de bewaarde RadioBox-historiek,
    oude Spotify-zoekresultaten of Duyster-archief. Nieuwe radioartiesten komen
    automatisch mee zodra de normale playlistscan ze vastlegt.
    """
    keys = cache.get('__playlist_keys', [])
    if not isinstance(keys, list):
        return set()
    artists = set()
    for key in keys:
        if not isinstance(key, str) or '|||' not in key:
            continue
        artist = key.split('|||', 1)[0]
        if norm(artist):
            artists.add(norm(artist))
    return artists


def prepare(cache, live_queue, seen, normalize_match):
    # v60: Duyster mag pas op basis van de echte playlist-cache kiezen.
    eligible_artists = playlist_artists(cache)
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
    # v62: handmatige Duyster-playlist als extra offline archiefbron.
    import v62_duyster_playlist_catalog
    catalog.update(v62_duyster_playlist_catalog.catalog(cache))
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
        print(f'🌙 v54: geen ontbrekende verwerkbare archiefkandidaten bij {len(eligible_artists)} playlist-artiesten')
        return
    active_duyster = sum(1 for x in live_queue if isinstance(x, dict) and x.get('source') == 'duyster')
    if active_duyster >= 3:
        return
    song = random.SystemRandom().choice(choices)
    key = normalize_match(song['artist']) + '|||' + normalize_match(song['title'])
    live_queue.append({'artist': song['artist'], 'title': song['title'], 'source': 'duyster'})
    issued[key] = now
    print(f'🌙 v60 playlist-artiest aanvullen: {song["artist"]} — {song["title"]} ({len(choices)} kandidaten)')
