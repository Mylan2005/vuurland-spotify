"""Read-only Spotify catalog verifier for historical Vuurland matcher misses.

Never writes to playlists, likes, queue, cache or seen state. Requires an
existing valid Spotify user refresh token in environment variables.
Input: Vuurland_volledige_beschikbare_matcher_audit_2026-11-22.json
       (the historical audit JSON with a top-level "tracks" list).
Output is an append-only JSONL checkpoint. Resume by running again.
No candidate is automatically approved for playlist insertion.
"""
import argparse
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import requests

SEARCH = "https://api.spotify.com/v1/search"
TOKEN = "https://accounts.spotify.com/api/token"


def canonical(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def strip_explicit_feature(title):
    """For searching only; the guest remains mandatory for evidence."""
    m = re.fullmatch(
        r"(.+?)\s*\((?:feat\.?|ft\.?|featuring|f\.?)\s+([^()]+)\)\s*",
        str(title or ""), flags=re.I,
    )
    return (m.group(1).strip(), m.group(2).strip()) if m else (str(title or "").strip(), None)


def classify(artist, title, hits):
    """Metadata evidence only. Not a replacement for the strict matcher."""
    core_title, guest = strip_explicit_feature(title)
    requested_artist, requested_title = canonical(artist), canonical(core_title)
    verified = []
    for item in hits[:10]:
        if not isinstance(item, dict):
            continue
        names = [a.get("name", "") for a in item.get("artists", [])
                 if isinstance(a, dict)]
        track_title, _ = strip_explicit_feature(item.get("name", ""))
        same_title = canonical(track_title) == requested_title
        same_artist = requested_artist in {canonical(n) for n in names}
        same_guest = not guest or canonical(guest) in {canonical(n) for n in names}
        verified.append({
            "spotify_id": item.get("id"),
            "spotify_title": item.get("name"),
            "artists": names,
            "album": (item.get("album") or {}).get("name"),
            "is_playable": item.get("is_playable"),
            "market_restriction": (item.get("restrictions") or {}).get("reason"),
            "metadata_matches": bool(same_title and same_artist and same_guest),
        })
    status = ("same_metadata_candidate_needs_version_review"
              if any(c["metadata_matches"] and c["is_playable"] is not False
                     and c["market_restriction"] != "market" for c in verified)
              else "candidate_requires_manual_review" if verified
              else "no_candidate_in_query")
    return status, verified


def spotify_access_token(session, client_id, refresh_token):
    response = session.post(TOKEN, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }, timeout=30)
    response.raise_for_status()
    access = response.json().get("access_token")
    if not access:
        raise RuntimeError("Spotify token ontbreekt")
    return access


def audit(input_path, output_path, *, max_queries=20, delay=8.0, market="BE",
          session=None, token=None, client_id=None, refresh_token=None):
    if not re.fullmatch(r"[A-Z]{2}", market):
        raise ValueError("Market moet een ISO-landcode zijn")
    if max_queries < 1 or delay < 0:
        raise ValueError("Ongeldige limieten")
    rows = json.loads(Path(input_path).read_text(encoding="utf-8"))["tracks"]
    if not isinstance(rows, list):
        raise ValueError("Auditinput mist tracks")
    output_path = Path(output_path)
    finished = set()
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                finished.add((record["artist"].casefold(), record["title"].casefold()))
    session = session or requests.Session()
    token = token or spotify_access_token(session, client_id, refresh_token)
    count = 0
    with output_path.open("a", encoding="utf-8") as out:
        for row in rows:
            artist, title = row["artist"], row["title"]
            key = (artist.casefold(), title.casefold())
            if key in finished:
                continue
            # Only 1 Search per track in this read-only audit run.
            # The existing production matcher is untouched.
            try:
                response = session.get(SEARCH, headers={"Authorization": "Bearer " + token},
                    params={"q": f'{artist} {title}', "type": "track",
                            "market": market, "limit": 10}, timeout=30)
            except requests.RequestException as error:
                raise RuntimeError("Spotify-netwerkfout; checkpoint behouden") from error
            if response.status_code == 429:
                raise RuntimeError("Spotify rate limit 429: veilig gestopt; later hervatten")
            if response.status_code in (401, 403):
                raise RuntimeError(f"Spotify authenticatie/toegang {response.status_code}")
            response.raise_for_status()
            candidates = response.json().get("tracks", {}).get("items", [])
            status, evaluated = classify(artist, title, candidates)
            out.write(json.dumps({
                "artist": artist, "title": title, "market": market,
                "status": status, "candidates": evaluated,
                "note": "Metadata evidence only; candidate must pass original Vuurland matcher",
            }, ensure_ascii=False) + "\n")
            out.flush()
            finished.add(key)
            count += 1
            if count >= max_queries:
                break
            if delay:
                time.sleep(delay)
    return {"searched_now": count, "total": len(rows), "completed_total": len(finished)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Historische audit JSON")
    parser.add_argument("--output", default="vuurland_catalog_audit.jsonl")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--market", default="BE")
    args = parser.parse_args()
    print(json.dumps(audit(args.input, args.output,
        max_queries=args.max_queries, delay=args.delay,
        market=args.market, client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        refresh_token=os.getenv("SPOTIFY_REFRESH_TOKEN"))))


if __name__ == "__main__":
    main()
