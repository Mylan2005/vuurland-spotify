#!/usr/bin/env python3
"""v259: daily READ-ONLY Spotify playlist duplicate audit across Vuurland volumes.

Compares live playlist items (including manual additions). Never deletes,
reorders, replaces, likes, or writes playlists. Spotify's removal endpoint does
not reliably support deleting only a later occurrence, so no auto-removal.
"""
import argparse
import collections
import datetime as dt
import json
import os
from pathlib import Path
import re
import time

import requests

API = "https://api.spotify.com/v1"
TOKEN = "https://accounts.spotify.com/api/token"
VOLUME_1 = "555lFTvdRswe9ukybmOM8T"
ID = re.compile(r"^[A-Za-z0-9]{22}$")
URI = re.compile(r"^spotify:track:[A-Za-z0-9]{22}$")


def volume_ids(cache):
    mapping = cache.get("__vuurland_volume_playlists")
    if not isinstance(mapping, dict):
        raise ValueError("Geen geldige Spotify volume-mapping in de state")
    mapping = {str(k): v for k, v in mapping.items()}
    if mapping.get("1") != VOLUME_1:
        raise ValueError("Volume 1 komt niet overeen met de vaste Vuurland-playlist")
    if "2" not in mapping:
        raise ValueError("Volume 2 ontbreekt: geen onvolledige dedupe-audit")
    numbered = sorted(int(n) for n in mapping if n.isdigit() and int(n)>0)
    if numbered != list(range(1, max(numbered)+1)):
        raise ValueError("Spotify-volumevolgorde onvolledig")
    ids = [(number, mapping[str(number)]) for number in numbered]
    if any(not isinstance(pid, str) or not ID.fullmatch(pid) for _, pid in ids):
        raise ValueError("Ongeldige Spotify-playlist-ID")
    if len({pid for _, pid in ids}) != len(ids):
        raise ValueError("Dubbele playlist-ID in volumes")
    return ids


def spotify_token(session, client_id, refresh_token):
    if not client_id or not refresh_token:
        raise ValueError("Spotify login ontbreekt; audit wordt overgeslagen")
    response = session.post(TOKEN, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }, timeout=30)
    response.raise_for_status()
    access_token = response.json().get("access_token")
    if not access_token:
        raise ValueError("Spotify gaf geen geldig access token")
    return access_token


def spotify_get(session, token, endpoint, *, params=None):
    # Strict allowlist: GET only, playlist read endpoints only.
    if not re.fullmatch(r"/playlists/[A-Za-z0-9]{22}(?:/items)?", endpoint):
        raise ValueError("Geen toegelaten Spotify leesendpoint")
    response = session.get(
        API + endpoint,
        params=params,
        headers={"Authorization": "Bearer " + token},
        timeout=30,
    )
    # Never retry 429 automatically; a scheduled audit must not compete with sync.
    if response.status_code == 429:
        raise RuntimeError("Spotify 429; audit veilig gestopt zonder retry")
    response.raise_for_status()
    return response.json()


def read_volume(session, token, number, playlist_id, pause=2.0):
    playlist = spotify_get(session, token, f"/playlists/{playlist_id}")
    snapshot_id = playlist.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError(f"Volume {number}: Spotify snapshot ontbreekt")
    result, offset, total = [], 0, None
    while True:
        page = spotify_get(
            session, token, f"/playlists/{playlist_id}/items",
            params={"limit": 50, "offset": offset},
        )
        items = page.get("items")
        if not isinstance(items, list):
            raise ValueError(f"Volume {number}: ongeldige playlistpagina")
        if total is None:
            total = page.get("total")
            if not isinstance(total, int) or total < 0 or total > 100_000:
                raise ValueError(f"Volume {number}: ongeldige totaalwaarde")
        if page.get("total") != total:
            raise RuntimeError("Playlist gewijzigd tijdens audit; geen gedeeltelijk rapport")
        result.extend(items)
        offset += len(items)
        if offset >= total:
            break
        if not items or offset > total:
            raise RuntimeError("Spotify-paginering is onvolledig")
        if pause:
            time.sleep(pause)
    if len(result) != total:
        raise RuntimeError(f"Volume {number}: paginering telt niet op")
    if pause:
        time.sleep(pause)
    after = spotify_get(session, token, f"/playlists/{playlist_id}")
    if after.get("snapshot_id") != snapshot_id:
        raise RuntimeError(f"Volume {number} wijzigde tijdens audit; opnieuw controleren bij volgende run")
    return {"number": number, "id": playlist_id,
            "snapshot_id": snapshot_id, "items": result}


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(dt.timezone.utc) if parsed.tzinfo else None


def audit(volumes, generated=None):
    if not isinstance(volumes, list) or not volumes:
        raise ValueError("Geen volumes")
    items = []
    seen_numbers = set()
    for volume in volumes:
        number = volume["number"]
        if number in seen_numbers:
            raise ValueError("Dubbel volumenummer")
        seen_numbers.add(number)
        raw_items = volume["items"]
        if not isinstance(raw_items, list):
            raise ValueError("Ongeldige playlistgegevens")
        for position, row in enumerate(raw_items):
            track = row.get("item", row.get("track")) if isinstance(row, dict) else None
            t = track if isinstance(track, dict) else {}
            uri = t.get("uri")
            if not isinstance(uri, str) or not URI.fullmatch(uri):
                uri = None
            artists = t.get("artists")
            first_artist = (artists[0].get("name", "") if isinstance(artists, list)
                            and artists and isinstance(artists[0], dict) else "")
            items.append({
                "volume": number, "position": position, "uri": uri,
                "artist": str(first_artist or ""), "title": str(t.get("name") or ""),
                "added_at": row.get("added_at") if isinstance(row, dict) else None,
            })
    by_uri = collections.defaultdict(list)
    for row in items:
        if row["uri"]:
            by_uri[row["uri"]].append(row)
    exact = []
    for uri, copies in by_uri.items():
        if len(copies) < 2:
            continue
        with_dates = all(_timestamp(x["added_at"]) is not None for x in copies)
        copies = sorted(copies, key=(
            (lambda x: (_timestamp(x["added_at"]), x["volume"], x["position"]))
            if with_dates else (lambda x: (x["volume"], x["position"]))
        ))
        exact.append({
            "uri": uri, "artist": copies[0]["artist"], "title": copies[0]["title"],
            "keep": {k: copies[0][k] for k in ("volume", "position", "added_at")},
            "duplicates": [{k: c[k] for k in ("volume", "position", "added_at")}
                           for c in copies[1:]],
            "oldest_verified_by_added_at": with_dates,
            "removal_approved": False,
        })
    exact.sort(key=lambda group: (group["keep"]["volume"], group["keep"]["position"]))
    # Same displayed title + artist, different URI: review only. Never use for deletions.
    by_name = collections.defaultdict(set)
    for row in items:
        if row["uri"] and row["artist"] and row["title"]:
            key = (row["artist"].casefold().strip(), row["title"].casefold().strip())
            by_name[key].add(row["uri"])
    review = [
        {"artist": artist, "title": title, "uris": sorted(uris),
         "removal_approved": False}
        for (artist, title), uris in sorted(by_name.items()) if len(uris) > 1
    ]
    return {
        "generated_utc": generated or dt.datetime.now(dt.timezone.utc).isoformat(),
        "read_only": True, "removed": 0, "total_items": len(items),
        "invalid_or_local_items": sum(x["uri"] is None for x in items),
        "volumes": [{"number": v["number"], "playlist_id": v["id"],
                     "snapshot_id": v["snapshot_id"], "count": len(v["items"])}
                    for v in volumes],
        "exact_uri_duplicates": exact,
        "repeat_occurrences": sum(len(x["duplicates"]) for x in exact),
        "different_uri_same_title_REVIEW_ONLY": review,
    }


def markdown(report):
    lines = [
        "# Vuurland — dagelijkse duplicatencontrole (v259)", "",
        f"Momentopname: {report['generated_utc']}", "",
        "**ALLEEN-LEZEN — niets verwijderd of gewijzigd op Spotify.**", "",
        f"- Nummers gecontroleerd: {report['total_items']}",
        f"- Identieke Spotify-URI's met herhalingen: {len(report['exact_uri_duplicates'])}",
        f"- Extra vermeldingen: {report['repeat_occurrences']}",
        f"- Gelijke artiest en titel, verschillende URI's (alleen nakijken): "
        f"{len(report['different_uri_same_title_REVIEW_ONLY'])}",
        f"- Lokale/onbruikbare items (niet beoordeeld): {report['invalid_or_local_items']}",
        "", "## Gecontroleerde volumes", "",
    ]
    for v in report["volumes"]:
        lines.append(f"- Volume {v['number']}: {v['count']} items (snapshot {v['snapshot_id']})")
    lines.extend(["", "## Exacte dubbels: oudste bewaren", ""])
    for item in report["exact_uri_duplicates"]:
        k = item["keep"]
        label = f"{item['artist']} — {item['title']}".replace("|", "/").replace("\n", " ")[:140]
        dest = ", ".join(f"Vol {x['volume']} positie {x['position']+1}"
                         for x in item["duplicates"])
        stamp = ("volgens toegevoegdatum" if item["oldest_verified_by_added_at"]
                 else "volgens volume/positie; datum niet volledig")
        lines.append(f"- **{label}**: behouden Vol {k['volume']} positie "
                     f"{k['position']+1} ({stamp}); extra: {dest}")
    if not report["exact_uri_duplicates"]:
        lines.append("- Geen identieke Spotify-URI's dubbel gevonden.")
    lines.extend(["", "## Zelfde naam, andere Spotify-URI: alleen nakijken", ""])
    for item in report["different_uri_same_title_REVIEW_ONLY"][:150]:
        label = f"{item['artist']} — {item['title']}".replace("|", "/").replace("\n", " ")[:140]
        lines.append(f"- {label} ({len(item['uris'])} Spotify-versies/URI's)")
    if len(report["different_uri_same_title_REVIEW_ONLY"]) > 150:
        lines.append("- Extra groepen staan in het downloadbare JSON-rapport.")
    lines.extend(["", "## Waarom geen automatische verwijdering?", "",
        "De huidige Spotify API kan bij een DELETE op een URI alle exemplaren "
        "verwijderen. Dat zou de oudste vermelding en handmatig toegevoegde muziek "
        "in gevaar brengen. Geen playlist herschrijven, geen Liked Songs wijzigen.",
        "Deze audit beïnvloedt je Spotify Search-budget, beurtrol, FIFO of playlists niet "
        "(wel afzonderlijke, voorzichtig gedoseerde playlist-GET-verzoeken).", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(".vuurland_spotify_cache.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("v259_dedup_rapport"))
    args = parser.parse_args()
    cache = json.loads(args.cache.read_text(encoding="utf-8"))
    with requests.Session() as session:
        token = spotify_token(session, os.getenv("SPOTIFY_CLIENT_ID"),
                              os.getenv("SPOTIFY_REFRESH_TOKEN"))
        volumes = [read_volume(session, token, number, playlist_id)
                   for number, playlist_id in volume_ids(cache)]
    report = audit(volumes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vuurland_dubbels.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (args.out_dir / "vuurland_dubbels.md").write_text(
        markdown(report), encoding="utf-8")
    print("✅ v259: dagelijkse audit (alleen lezen) — "
          f"{report['total_items']} items, {report['repeat_occurrences']} herhalingen, 0 verwijderd.")


if __name__ == "__main__":
    main()
