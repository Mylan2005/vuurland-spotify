"""Weekly, Spotify-free Duyster archive intake from duyster-online.be.

Only the next published episode is checked; a missing/unfinished page never
advances the episode cursor. This file is invoked by its own Wednesday workflow,
NOT by the one-minute Spotify sync.
"""
import csv
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from duyster_archive_fifo import is_non_music_title

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "duyster_archief_uniek.csv"
STATE = ROOT / "duyster_archief_import_state.json"
BASE = "https://duyster-online.be/playlist.php?pid="
MAX_EPISODES_PER_CHECK = 8
MIN_PLAYLIST_ENTRIES = 5
HEADERS = {"User-Agent": "VuurlandDuysterArchive/1.0 (+weekly music metadata fetch)"}
CSV_FIELDS = ("artist", "title", "first_seen_pid", "seen_in")


def song_key(artist, title):
    def normalize(value):
        value = unicodedata.normalize("NFKD", str(value or "").casefold())
        value = "".join(c for c in value if not unicodedata.combining(c))
        return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()
    return normalize(artist) + "|||" + normalize(title)


def parse_episode(html, pid):
    """Return metadata for exactly this numbered, published episode or None."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.get_text(" ", strip=True)
    if not re.search(r"\bplaylist\s+nr\.?\s*" + str(pid) + r"\b", body, re.I):
        return None
    date = re.search(r"\b\d{2}-\d{2}-\d{4}\b", body)
    episode_date = date.group(0) if date else None
    songs, unique = [], set()
    raw_count = 0
    for link in soup.select("a[href]"):
        target = urlsplit(urljoin(BASE, link["href"]))
        if not target.path.lower().endswith("/library/songs.php"):
            continue
        params = {k.casefold(): v for k, v in parse_qs(target.query).items()}
        artist = str((params.get("artiest") or [""])[0]).strip()
        title = str((params.get("titel") or [""])[0]).strip()
        if not artist or not title or len(artist) > 150 or len(title) > 300:
            continue
        raw_count += 1
        if is_non_music_title(title):
            continue
        key = song_key(artist, title)
        if key in unique:
            continue
        unique.add(key)
        songs.append((artist, title))
    if raw_count < MIN_PLAYLIST_ENTRIES:
        return None
    return {"pid": pid, "date": episode_date, "songs": songs,
            "skipped_non_music": raw_count - len(songs)}


def get_episode(pid, *, request_get=requests.get):
    response = request_get(BASE + str(pid), headers=HEADERS, timeout=15)
    if response.status_code in (404, 410):
        return None
    response.raise_for_status()
    return parse_episode(response.text, pid)


def read_archive(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError("Ongeldige Duyster-archiefkolommen")
        rows = list(reader)
    result = {}
    for index, row in enumerate(rows):
        key = song_key(row["artist"], row["title"])
        if key in result:
            raise ValueError("Duyster-archief bevat een dubbele sleutel: " + key)
        result[key] = index
    return rows, result


def read_state(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        state = json.load(stream)
    next_pid = state.get("next_pid")
    if type(next_pid) is not int or next_pid < 834:
        raise ValueError("Duyster-afleveringcursor ongeldig; archief onveranderd")
    return state


def atomic_write(path, content):
    target = Path(path)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix="." + target.name + ".")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as out:
            out.write(content)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_archive(*, archive=ARCHIVE, state_file=STATE, get_page=get_episode):
    """Import subsequent episodes only after verifying all their metadata."""
    state = read_state(state_file)
    rows, lookup = read_archive(archive)
    next_pid = state["next_pid"]
    episodes = []
    for pid in range(next_pid, next_pid + MAX_EPISODES_PER_CHECK):
        episode = get_page(pid)
        if episode is None:
            print(f"📻 Duyster aflevering {pid} nog niet gepubliceerd of niet volledig.")
            break
        if episode["pid"] != pid or not episode["songs"]:
            raise ValueError("Duyster antwoord onvolledig of verkeerde aflevering")
        episodes.append(episode)
    if not episodes:
        print("ℹ️ Geen nieuwe Duyster-aflevering; archief en cursor onveranderd.")
        return 0

    added, repeats, blocked = 0, 0, 0
    for episode in episodes:
        for artist, title in episode["songs"]:
            if is_non_music_title(title):
                blocked += 1
                continue
            key = song_key(artist, title)
            if key in lookup:
                index = lookup[key]
                rows[index]["seen_in"] = str(int(rows[index]["seen_in"]) + 1)
                repeats += 1
            else:
                lookup[key] = len(rows)
                rows.append({"artist": artist, "title": title,
                             "first_seen_pid": str(episode["pid"]), "seen_in": "1"})
                added += 1
        blocked += episode["skipped_non_music"]
    # Keep the original CRLF CSV style, so the GitHub diff contains only
    # the changed rows plus new titles, never a full archive rewrite.
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)

    state["last_imported_pid"] = episodes[-1]["pid"]
    state["next_pid"] = episodes[-1]["pid"] + 1
    state["last_imported_at_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_write(archive, buffer.getvalue())
    atomic_write(state_file, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    print(f"✅ Duyster afleveringen {episodes[0]['pid']}–{episodes[-1]['pid']}: "
          f"{added} nieuwe nummers, {repeats} eerder bekende plays, "
          f"{blocked} interview/sessie-vermeldingen genegeerd. "
          f"Archief: {len(rows)} unieke muziekstukken.")
    return len(episodes)


if __name__ == "__main__":
    try:
        update_archive()
    except (OSError, requests.RequestException, ValueError, csv.Error,
            UnicodeError, json.JSONDecodeError) as error:
        print(f"❌ Duyster-update veilig gestopt, geen automatische playlistwijziging: {error}",
              file=sys.stderr)
        sys.exit(1)
