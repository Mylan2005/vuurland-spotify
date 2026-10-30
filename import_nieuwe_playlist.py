#!/usr/bin/env python3
"""Read-only Spotify inventory import; updates only local dedupe cache after full verification."""
import json
import os
import time
from pathlib import Path
import requests
from vuurland_sync import make_playlist_keys, atomic_save_json

PLAYLIST_ID = os.environ.get("VUURLAND_PLAYLIST_ID", "555lFTvdRswe9ukybmOM8T")
EXPECTED = 2733
CACHE = Path(".vuurland_spotify_cache.json")
BASE = "https://api.spotify.com/v1"

def main():
    cid = os.environ["SPOTIFY_CLIENT_ID"]
    refresh = os.environ["SPOTIFY_REFRESH_TOKEN"]
    auth = requests.post("https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": cid},
        timeout=30)
    auth.raise_for_status()
    token = auth.json()["access_token"]
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + token})

    def scan(path, limit):
        offset = 0
        expected_total = None
        records = []
        while True:
            response = session.get(BASE + path, params={"limit": limit, "offset": offset}, timeout=40)
            if response.status_code == 429:
                raise RuntimeError("Spotify 429: stop zonder cache-update; probeer later opnieuw")
            response.raise_for_status()
            page = response.json()
            rows, total = page.get("items"), page.get("total")
            if not isinstance(rows, list) or not isinstance(total, int):
                raise RuntimeError("Ongeldige Spotify-pagina; cache niet bijgewerkt")
            if expected_total is None:
                expected_total = total
            if total != expected_total or not rows and page.get("next"):
                raise RuntimeError("Spotify-inhoud veranderde tijdens scan")
            for entry in rows:
                track = entry.get("item") or entry.get("track") or {}
                if track.get("type") != "track" or not track.get("id") or not track.get("name") or not track.get("artists"):
                    raise RuntimeError("Niet-herkende track; cache niet bijgewerkt")
                records.append(track)
            offset += len(rows)
            if not page.get("next"):
                if offset != expected_total:
                    raise RuntimeError(f"Onvolledige scan: {offset}/{expected_total}")
                break
            if offset > 100000:
                raise RuntimeError("Te veel pagina's")
            time.sleep(.25)
        return records

    playlist = scan(f"/playlists/{PLAYLIST_ID}/items", 100)
    liked = scan("/me/tracks", 50)
    playlist_ids = [t["id"] for t in playlist]
    liked_ids = [t["id"] for t in liked]
    print(f"Playlist: {len(playlist)}; Liked Songs: {len(liked)}")
    if (len(playlist) != EXPECTED or len(liked) != EXPECTED
            or len(set(playlist_ids)) != EXPECTED or len(set(liked_ids)) != EXPECTED
            or set(playlist_ids) != set(liked_ids)):
        raise RuntimeError("Aantallen/IDs verschillen; GEEN cachewijziging")
    keys, uris, isrcs, uri_isrc = set(), set(), set(), {}
    for t in playlist:
        keys.update(make_playlist_keys(t))
        uri = t.get("uri") or "spotify:track:" + t["id"]
        uris.add(uri)
        isrc = str((t.get("external_ids") or {}).get("isrc") or "").strip().upper()
        if isrc:
            isrcs.add(isrc)
            uri_isrc[uri] = isrc
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if not isinstance(cache, dict):
        raise RuntimeError("Onverwachte cachevorm")
    # Invalidate old/partial scans; populate same dedupe fields as main sync.
    cache.update({
        "__playlist_keys": sorted(keys),
        "__playlist_uris": sorted(uris),
        "__playlist_isrcs": sorted(isrcs),
        "__spotify_uri_isrc": uri_isrc,
        "__playlist_isrc_cache_ready": True,
        "__playlist_cache_time": int(time.time()),
        "__vuurland_active_volume": 1,
        "__vuurland_active_playlist_id": PLAYLIST_ID,
        "__vuurland_active_playlist_count": len(playlist),
        "__vuurland_volume_playlists": {"1": PLAYLIST_ID},
        "__v164_playlist_count_checked_at": int(time.time()),
        "__v184_head_playlist_id": PLAYLIST_ID,
        "__v184_head_checked_at": int(time.time()),
    })
    # Do not claim the full sync's migration/import milestones have run.
    cache.pop("__v166_playlist_scan", None)
    cache.pop("__v177_playlist_delta", None)
    atomic_save_json(str(CACHE), cache)
    print(f"✅ {len(playlist)} tracks volledig ingelezen; {len(keys)} matcher-sleutels, {len(isrcs)} ISRC's.")
    print("✅ Liked Songs bevatten exact dezelfde Spotify-track-ID's. Geen Spotify-nummers gewijzigd.")

if __name__ == "__main__":
    main()
