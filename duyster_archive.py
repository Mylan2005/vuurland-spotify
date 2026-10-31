"""Duyster episode archive: bounded historic import and shuffled live-queue discovery."""
import random
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = "https://duyster-online.be/"
ARCHIVE = "__duyster_archive_episodes_v1"
CURSOR = "__duyster_archive_next_v1"
LATEST = "__duyster_archive_latest_v1"
LATEST_AT = "__duyster_archive_latest_at_v1"
EMITTED = "__duyster_last_emission_v1"
USED = "__duyster_used_v1"


def fetch(url):
    try:
        response = requests.get(url, timeout=8, headers={"User-Agent": "VuurlandRadio/1.0"})
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        print(f"⚠️ Duyster archief tijdelijk niet beschikbaar: {exc}")
        return None


def songs_from_page(html):
    soup = BeautifulSoup(html, "html.parser")
    result, seen = [], set()
    for a in soup.select("a[href]"):
        url = urlparse(urljoin(ROOT, a["href"]))
        if not url.path.lower().endswith("/library/songs.php"):
            continue
        qs = parse_qs(url.query)
        artist = (qs.get("Artiest") or qs.get("artiest") or [""])[0].strip()
        title = (qs.get("Titel") or qs.get("titel") or [""])[0].strip()
        if not artist or not title or len(artist) > 150 or len(title) > 300:
            continue
        if re.search(r"\(\s*(sessie|interview)\s*\)", title, re.I):
            continue
        ident = (artist.casefold(), title.casefold())
        if ident not in seen:
            seen.add(ident)
            result.append([artist, title])
    return result


def run(cache, queue, already_known, key_fn):
    """Never touch another source; emit <=1 Duyster track per 60 s.

    Backfill five episode pages each round and avoid adding any songs until
    the complete historic range has been scanned once.
    """
    now = time.time()
    archive = cache.setdefault(ARCHIVE, {})
    if not isinstance(archive, dict):
        return 0
    latest = cache.get(LATEST)
    if not isinstance(latest, int) or now - float(cache.get(LATEST_AT, 0) or 0) >= 3600:
        html = fetch(urljoin(ROOT, "playlist.php"))
        match = re.search(r"playlist\s+nr\.?\s*(\d+)", BeautifulSoup(html, "html.parser").get_text(" ", strip=True), re.I) if html else None
        if match:
            latest = max(int(latest or 0), int(match.group(1)))
            cache[LATEST] = latest
            cache[LATEST_AT] = now
    if not isinstance(latest, int) or latest < 1:
        print("⏳ Duyster: meest recente aflevering nog onbekend.")
        return 0

    # Pick up newly published episodes, independently of the historic cursor.
    if str(latest) not in archive:
        html = fetch(urljoin(ROOT, f"playlist.php?pid={latest}"))
        if html:
            tracks = songs_from_page(html)
            if tracks:
                archive[str(latest)] = tracks

    cursor = cache.get(CURSOR)
    if not isinstance(cursor, int):
        cursor = latest
    cursor = min(cursor, latest)
    attempts = 0
    while cursor > 0 and attempts < 5:
        ident = str(cursor)
        if ident not in archive:
            html = fetch(urljoin(ROOT, f"playlist.php?pid={cursor}"))
            if html is None:
                break
            archive[ident] = songs_from_page(html)
        cursor -= 1
        attempts += 1
    cache[CURSOR] = cursor
    print(f"📚 Duyster: {len(archive)} afleveringen opgeslagen; "
          f"{cursor} oudere nummers van afleveringen nog na te kijken.")
    if cursor > 0 or now - float(cache.get(EMITTED, 0) or 0) < 60:
        return 0

    used = cache.setdefault(USED, [])
    if not isinstance(used, list):
        return 0
    blocked = set(already_known) | set(used)
    options = []
    for episode, tracks in archive.items():
        for entry in tracks:
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            artist, title = entry
            key = key_fn(artist, title)
            if key not in blocked:
                options.append((artist, title, key, episode))
    if not options:
        print("ℹ️ Duyster: geen nog beschikbare archiefnummers.")
        return 0
    artist, title, key, episode = random.SystemRandom().choice(options)
    queue.append({"artist": artist, "title": title, "source": "duyster",
                  "duyster_episode": episode})
    used.append(key)
    cache[EMITTED] = now
    print(f"🎲 Duyster aflevering {episode}: {artist} - {title} in wachtrij.")
    return 1
