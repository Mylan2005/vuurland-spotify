"""Duyster als derde wachtrijbron; geen zelfstandige Spotify-API-calls.

De Spotify-matcher, ISRC-controle en 1-Search-limiet blijven in vuurland_sync.py.
De checkpoint van nieuwe afleveringen en de importstatus worden in de bestaande
Spotify-cache opgeslagen, die al door de workflow wordt gesynchroniseerd.
"""
import csv
import os
import random
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

BASE = 'https://www.duyster-online.be/playlist.php?pid='
ARCHIVE_CSV = Path(__file__).with_name('duyster_archief_uniek.csv')
START_PID = 832
REQUEST_TIMEOUT = 15
RETRY_SECONDS = 86400
MAX_ACTIVE_DUYSTER = 3  # Een wachtende retry mag de shuffle niet blokkeren.
# v52.4: auditlijst eerst reviewen; standaard geen Spotify-only toevoegingen.
SPOTIFY_ONLY_CSV = Path(__file__).with_name('duyster_spotify_only_v52_4.csv')
SPOTIFY_ONLY_ENABLED = False


# Bevestigde foutieve archiefregel. Niet zoeken of opnieuw selecteren.
EXCLUDED_ARCHIVE_SONGS = {
    (". . - . . - ... . - ..", ".. / ..-. --- .-. --. --- - / - --- / - .- -.- . / -- -.-- / -- . -.. ..."),
}

def _excluded(artist, title):
    if (str(artist).strip(), str(title).strip()) in EXCLUDED_ARCHIVE_SONGS:
        return True
    # v52.2: exacte ontbrekende-titel-placeholders zijn geen zoekbare tracks.
    # Geen brede "untitled"-filter: Untitled is soms een echte songtitel.
    if re.fullmatch(
        r"(?i)\s*(?:unknown[ -]+(?:song|track|title)|(?:song|track|title)[ -]+unknown|"
        r"onbekend[ -]+nummer|nummer[ -]+onbekend|onbekende[ -]+titel|"
        r"(?:no|geen)[ -]+(?:song[ -]+)?title)\s*",
        str(title or ""),
    ):
        return True
    # v51: archiefsessie is geen los muzieknummertitel.
    if re.fullmatch(r"(?i)\s*(?:sessie|session|interview\s*[+&]\s*sessie)\s*", str(title or '')):
        return True
    # v48: interviews zijn geen muzieknummers en mogen geen shuffleplaats innemen.
    return bool(re.match(
        r"(?i)^\s*interview(?:\s*(?:\(|\[|:|[-–—]|with\b|met\b|w/\b|\d{1,3}\b)|\s*$)",
        str(title or "").strip(),
    ))


class SongLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.songs = []

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        url = dict(attrs).get('href', '')
        parsed = urlsplit(url.replace('&amp;', '&'))
        if not parsed.path.endswith('/library/songs.php') and not parsed.path.endswith('library/songs.php'):
            return
        params = parse_qs(parsed.query)
        artist = (params.get('Artiest') or [''])[0].strip()
        title = (params.get('Titel') or [''])[0].strip()
        if artist and title:
            self.songs.append((artist, title))


def _key(artist, title):
    return artist.strip().casefold() + '\x1f' + title.strip().casefold()


def _seen_key(normalize_match, artist, title):
    return normalize_match(artist) + '|||' + normalize_match(title)


def _songs(cache):
    # Het volledige historische CSV is onveranderlijk startmateriaal. Nieuwe
    # afleveringen worden apart in de reeds gesynchroniseerde cache bewaard.
    catalog = {}
    if not ARCHIVE_CSV.is_file():
        raise FileNotFoundError(f'Duyster-bron ontbreekt: {ARCHIVE_CSV}')
    with ARCHIVE_CSV.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if (row.get('artist') and row.get('title')
                    and not _excluded(row['artist'], row['title'])):
                catalog[_key(row['artist'], row['title'])] = {
                    'artist': row['artist'], 'title': row['title']
                }
    for key, song in cache.get('__duyster_new_songs', {}).items():
        if not _excluded(song.get('artist', ''), song.get('title', '')):
            catalog[key] = song
    return catalog


def check_new_episode(cache):
    """Maximaal één archief-HTTP-aanvraag per ronde; geen Spotify-verkeer."""
    pid = max(START_PID, int(cache.get('__duyster_next_pid', START_PID)))
    try:
        response = requests.get(BASE + str(pid), timeout=REQUEST_TIMEOUT,
                                headers={'User-Agent': 'VuurlandDuysterArchive/1.0'})
        response.raise_for_status()
        html = response.text
        parser = SongLinks()
        parser.feed(html)
        songs = list(dict.fromkeys(parser.songs))
    except requests.RequestException as error:
        print(f'🟡 Duyster aflevering {pid}: tijdelijk niet bereikbaar: {error}')
        return
    except Exception as error:
        print(f'🟡 Duyster aflevering {pid}: niet te verwerken: {error}')
        return

    # Een blanco of afwijkende pagina is NOOIT een bevestiging dat deze
    # aflevering verwerkt is. Laat pid staan en probeer later opnieuw.
    if not songs:
        print(f'📚 Duyster aflevering {pid} nog niet leesbaar; later opnieuw.')
        return

    new = dict(cache.get('__duyster_new_songs', {}))
    fresh = 0
    for artist, title in songs:
        if _excluded(artist, title):
            continue
        key = _key(artist, title)
        if key not in new:
            # De historische CSV wordt bij selectie eveneens afgetoetst.
            new[key] = {'artist': artist, 'title': title}
            fresh += 1
    cache['__duyster_new_songs'] = new
    cache['__duyster_next_pid'] = pid + 1
    print(f'📚 Duyster aflevering {pid}: {len(songs)} nummers; '
          f'{fresh} kandidaat-records opgeslagen (historische dubbels worden genegeerd).')


def enqueue_one(cache, live_queue, seen, normalize_match):
    """Voeg hoogstens één willekeurig nummer toe, zonder vorige resultaten te herhalen."""
    catalog = _songs(cache)
    active = {
        _seen_key(normalize_match, x.get('artist', ''), x.get('title', ''))
        for x in live_queue if isinstance(x, dict)
    }
    # v50: afgehandelde niet-vindbare archiefnummers niet opnieuw loten.
    # Ook oude v49-herprobeerrecords tellen als definitief afgehandeld.
    blocked = set(cache.get('__v50_duyster_unmatched', {}))
    blocked.update(key for key, entry in cache.get('__v47_failed_tracks', {}).items()
                   if isinstance(entry, dict) and entry.get('source') == 'duyster')
    issued = dict(cache.get('__duyster_issued', {}))
    now = int(time.time())
    eligible = []
    done = 0
    for song in catalog.values():
        key = _seen_key(normalize_match, song['artist'], song['title'])
        if key in blocked:
            continue
        if key in seen:
            done += 1
            continue
        if key in active:
            continue
        # Als een oudere zoekactie eindigde zonder 'seen' (bijvoorbeeld na
        # drie mislukte varianten), pas na 24 uur opnieuw overwegen.
        last = int(issued.get(key, 0) or 0)
        if last and now - last < RETRY_SECONDS:
            continue
        eligible.append(song)
    if not eligible:
        print(f'📚 Duyster: geen kandidaat beschikbaar; {done}/{len(catalog)} in seen; {len(issued)} ooit geselecteerd.')
        return False
    song = random.SystemRandom().choice(eligible)
    key = _seen_key(normalize_match, song['artist'], song['title'])
    live_queue.append({'artist': song['artist'], 'title': song['title'],
                       'source': 'duyster'})
    issued[key] = now
    cache['__duyster_issued'] = issued
    print(f'🎲 Duyster shuffle: {song["artist"]} — {song["title"]} '
          f'({done}/{len(catalog)} in seen; {len(issued)} ooit geselecteerd).')
    return True



def load_spotify_only_candidates(path=SPOTIFY_ONLY_CSV):
    """Strict read-only audit data. Unconfirmed entries are never queued."""
    if not path.is_file():
        return {}
    candidates = {}
    blocked = set()
    with path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            if row.get('review_status') != 'approved':
                continue
            artist = (row.get('artiest') or '').strip()
            title = (row.get('titel') or '').strip()
            track_id = (row.get('spotify_track_id') or '').strip()
            isrc = (row.get('isrc') or '').strip().upper()
            if not (artist and title and re.fullmatch(r'[A-Za-z0-9]{22}', track_id)
                    and re.fullmatch(r'[A-Za-z0-9]{12}', isrc)
                    and row.get('spotify_url') == 'https://open.spotify.com/track/' + track_id):
                continue
            if row.get('is_playable_api', '').casefold() != 'true':
                continue
            key = _key(artist, title)
            entry = {'artist': artist, 'title': title,
                     'spotify_track_id': track_id, 'isrc': isrc}
            if key in candidates and candidates[key] != entry:
                blocked.add(key)
            candidates[key] = entry
    for key in blocked:
        candidates.pop(key, None)
    return candidates


def enqueue_spotify_only(cache, live_queue, seen, normalize_match, candidates):
    """One Spotify-only Duyster item, never a fourth radio source."""
    active = {_seen_key(normalize_match, x.get('artist', ''), x.get('title', ''))
              for x in live_queue if isinstance(x, dict)}
    # The issued map is a *cooldown*, not a permanent completion marker.
    # A song is complete only after the normal sync records it in `seen`.
    issued = cache.setdefault('__v524_spotify_only_issued', {})
    now = int(time.time())
    eligible = []
    for entry in candidates.values():
        key = _seen_key(normalize_match, entry['artist'], entry['title'])
        if key in active or key in seen:
            continue
        last_issued = int(issued.get(key, 0) or 0)
        if last_issued and now - last_issued < RETRY_SECONDS:
            continue
        eligible.append(entry)
    if not eligible:
        return False
    # Deterministic ordering; a vanished/failed queue item is retried after
    # cooldown instead of being silently lost forever.
    choice = eligible[0]
    key = _seen_key(normalize_match, choice['artist'], choice['title'])
    live_queue.append({'artist': choice['artist'], 'title': choice['title'],
                       'source': 'duyster', '_v524_spotify_only': True})
    issued[key] = now
    print(f'🔗 Duyster Spotify-only kandidaat: {choice["artist"]} — {choice["title"]}')
    return True

def prepare(cache, live_queue, seen, normalize_match):
    # Nieuwe uitzending komt meteen in de catalogus, ook tijdens de backlog.
    check_new_episode(cache)
    # Een Duyster-track die 10 minuten wacht op een volgende zoekvariant
    # mag nieuwe archiefselecties niet stilleggen. Houd de buffer klein:
    # maximaal drie openstaande Duyster-tracks, geen extra Spotify-calls.
    now = time.time()
    active_duyster = [item for item in live_queue
                      if isinstance(item, dict) and item.get('source') == 'duyster']
    if len(active_duyster) >= MAX_ACTIVE_DUYSTER:
        return
    # Is er al een Duyster-track NU verwerkbaar, maak geen extra queue-item.
    # De globale scheduler geeft radio prioriteit en laat Duyster daarna toe.
    if any(int(item.get('_v34_retry_at', 0) or 0) <= now
           for item in active_duyster):
        return
    # v52.4: opt-in, and only vetted rows. Alternate Duyster internal slots.
    # RadioBox source_order and global 2/round limit remain in sync.py.
    if SPOTIFY_ONLY_ENABLED:
        candidates = load_spotify_only_candidates()
        if candidates and cache.get('__v524_duyster_next_kind', 'archive') == 'spotify_only':
            if enqueue_spotify_only(cache, live_queue, seen, normalize_match, candidates):
                cache['__v524_duyster_next_kind'] = 'archive'
                return
    if enqueue_one(cache, live_queue, seen, normalize_match):
        if SPOTIFY_ONLY_ENABLED:
            cache['__v524_duyster_next_kind'] = 'spotify_only'
        return
    # Archive exhausted: eligible vetted Spotify-only records may still progress.
    if SPOTIFY_ONLY_ENABLED:
        enqueue_spotify_only(cache, live_queue, seen, normalize_match,
                             load_spotify_only_candidates())
