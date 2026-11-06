#!/usr/bin/env python3
"""v204: Spotify Dedup-inspired OFFLINE review, never an automatic remover.

Input: an explicitly exported JSON playlist snapshot (list of Spotify track
objects or playlist item {"track": ...}/{"item": ...} wrappers). A Spotify
cache of historical known URI/ISRCs is NOT a snapshot of a current playlist.
No network, no token, no writes to source, no removal, no live queue changes.
"""
import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


def norm(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(text.split())


def clean_track(raw, position):
    if not isinstance(raw, dict):
        return None
    track = raw.get("track", raw.get("item", raw))
    if not isinstance(track, dict):
        return None
    uri = track.get("uri")
    name = track.get("name")
    artists = track.get("artists")
    if not (isinstance(uri, str) and re.fullmatch(r"spotify:track:[A-Za-z0-9]{22}", uri)
            and isinstance(name, str) and name.strip()
            and isinstance(artists, list) and artists):
        return None
    primary = artists[0].get("name") if isinstance(artists[0], dict) else None
    if not isinstance(primary, str) or not primary.strip():
        return None
    duration = track.get("duration_ms")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
        duration = None
    identifiers = track.get("external_ids") or {}
    isrc = identifiers.get("isrc") if isinstance(identifiers, dict) else None
    isrc = isrc.strip().upper() if isinstance(isrc, str) else ""
    if not re.fullmatch(r"[A-Z0-9]{12}", isrc):
        isrc = ""
    return {
        "position": position,
        "uri": uri,
        "name": name.strip(),
        "artist": primary.strip(),
        "duration_ms": duration,
        "isrc": isrc,
    }


def analyze(items):
    """Only exact URI / ISRC groups are strong duplicate evidence.

    Equal artist+title+near duration from JMPerez/spotify-dedup is a review
    *candidate*, never automatic proof: different masters, covers, edits,
    remixes and live performances can have near-equal length.
    """
    if not isinstance(items, list):
        raise ValueError("Verwacht een JSON-lijst met playlistitems")
    tracks = []
    skipped = 0
    for i, raw in enumerate(items):
        row = clean_track(raw, i)
        if row is None:
            skipped += 1
        else:
            tracks.append(row)
    by_uri = defaultdict(list)
    by_isrc = defaultdict(list)
    by_title = defaultdict(list)
    for row in tracks:
        by_uri[row["uri"]].append(row)
        if row["isrc"]:
            by_isrc[row["isrc"]].append(row)
        by_title[(norm(row["artist"]), norm(row["name"]))].append(row)

    exact_uri = [
        {"uri": uri, "positions": [r["position"] for r in rows]}
        for uri, rows in by_uri.items() if len(rows) > 1
    ]
    same_isrc_different_uri = []
    for isrc, rows in by_isrc.items():
        uris = sorted(set(r["uri"] for r in rows))
        if len(uris) > 1:
            same_isrc_different_uri.append({
                "isrc": isrc, "uris": uris,
                "positions": [r["position"] for r in rows],
            })

    # Suppress observations already explained by matching URI/ISRC.
    review_only = []
    for (artist, title), rows in by_title.items():
        for i, a in enumerate(rows):
            for b in rows[i+1:]:
                if a["uri"] == b["uri"]:
                    continue
                if a["isrc"] and b["isrc"] and a["isrc"] == b["isrc"]:
                    continue
                if (a["duration_ms"] is not None and b["duration_ms"] is not None
                        and abs(a["duration_ms"] - b["duration_ms"]) < 2000):
                    review_only.append({
                        "artist": a["artist"], "title": a["name"],
                        "positions": [a["position"], b["position"]],
                        "uris": [a["uri"], b["uri"]],
                        "duration_delta_ms": abs(a["duration_ms"] - b["duration_ms"]),
                        "isrcs": [a["isrc"], b["isrc"]],
                        "approved_for_removal": False,
                    })
    return {
        "scope": "uitsluitend aangeleverde playlist-snapshot; niet de historische dedupe-cache",
        "spotify_requests": 0, "removed": 0,
        "total_valid_tracks": len(tracks), "skipped_unusable": skipped,
        "exact_uri_repetitions": sorted(exact_uri, key=lambda x: x["positions"][0]),
        "same_isrc_different_uri": sorted(same_isrc_different_uri, key=lambda x: x["positions"][0]),
        "same_artist_title_duration_REVIEW_ONLY": sorted(review_only, key=lambda x: x["positions"]),
        "warning": "NOOIT automatisch verwijderen op basis van titel/artiest/speelduur; bevestig de opname handmatig.",
    }


def markdown(report):
    lines = [
        "# Vuurland v204 — alleen-lezen duplicatencontrole", "",
        "**Er is niets verwijderd, aangepast of opgezocht via Spotify.**", "",
        "Dit is een momentopname uit een aangeleverde playlist-export; "
        "géén uitspraak over andere volumes of je volledige Spotify-bibliotheek.",
        "", f"- Geldige playlistposities: {report['total_valid_tracks']}",
        f"- Overgeslagen onbruikbare items: {report['skipped_unusable']}",
        f"- Herhaalde identieke Spotify-URI's: {len(report['exact_uri_repetitions'])}",
        f"- Verschillende URI's met dezelfde ISRC: {len(report['same_isrc_different_uri'])}",
        f"- Zelfde titel/artiest, < 2s verschil (ALLEEN NAKIJKEN): {len(report['same_artist_title_duration_REVIEW_ONLY'])}",
        "", "## Identieke Spotify-URI's", "",
    ]
    for row in report["exact_uri_repetitions"]:
        lines.append(f"- Posities {row['positions']}: {row['uri']}")
    lines.extend(["", "## Zelfde ISRC, andere URI", ""])
    for row in report["same_isrc_different_uri"]:
        lines.append(f"- ISRC {row['isrc']}: posities {row['positions']}; {', '.join(row['uris'])}")
    lines.extend(["", "## Alleen ter beoordeling: gelijke naam en bijna gelijke duur", "",
                  "Titel/artiest/duur zijn **geen bewijs van dezelfde opname**.", ""])
    for row in report["same_artist_title_duration_REVIEW_ONLY"]:
        label = f"{row['artist']} — {row['title']}".replace("\n", " ")[:160]
        lines.append(f"- {label}: posities {row['positions']}, verschil "
                     f"{row['duration_delta_ms']} ms, ISRCs {row['isrcs']}")
    lines.extend(["", "## Veiligheid", "",
                  "Geen automatische playlist- of Liked Songs-verwijderingen. "
                  "Vuurland behoudt de bestaande URI/ISRC-checks, FIFO en Spotify-limieten.",
                  "JMPerez/spotify-dedup is een aparte tool om doublures na controle "
                  "handmatig te beheren; de namen/duurheuristiek wordt hier nooit "
                  "als toestemming tot verwijderen gebruikt.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True,
                        help="Expliciete JSON-export van een Spotify-playlist")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        payload = payload["items"]
    result = analyze(payload)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vuurland_v204_duplicaten.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "vuurland_v204_duplicaten.md").write_text(
        markdown(result), encoding="utf-8")
    print(f"✅ Alleen-lezen audit van {result['total_valid_tracks']} items; "
          f"0 Spotify-calls, 0 verwijderingen.")


if __name__ == "__main__":
    main()
