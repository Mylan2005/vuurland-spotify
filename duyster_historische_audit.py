#!/usr/bin/env python3
"""v206: auditeer IEDERE Duyster-aflevering, herstel ontbrekende muziek.

De gewone wekelijkse import onthoudt enkel de hoogste aflevering. Dit is
onvoldoende bewijs dat alle titels uit vorige afleveringen aanwezig zijn.

Deze tool vergelijkt bronpagina's opnieuw, beginnend bij de nieuwste, daarna
alle afleveringen in omgekeerde volgorde; controleert ieder bronnummer tegen de
archief-sleutel en voegt uitsluitend ontbrekende artiest/titelparen toe.
Uitval = cursor vasthouden, nooit onterecht 'compleet' rapporteren.

Geen Spotify-requests, geen playlist/likes/FIFO-mutaties en geen fuzzy match.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from duyster_weekly_update import (
    ARCHIVE, STATE, atomic_write, get_episode, read_archive, read_state,
    song_key, CSV_FIELDS,
)

ROOT = Path(__file__).resolve().parent
AUDIT_STATE = ROOT / "duyster_historische_audit_state.json"
LATEST_PRIORITY_COUNT = 3
DEFAULT_BATCH = 60
MAX_BATCH = 80
MIN_DELAY_SECONDS = 0.8
RECHECK_AFTER_DAYS = 30


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _valid_episode(episode, pid):
    if not isinstance(episode, dict) or episode.get("pid") != pid:
        raise ValueError(f"Duyster aflevering {pid} ontbreekt of is onvolledig")
    songs = episode.get("songs")
    if not isinstance(songs, list) or len(songs) < 5:
        raise ValueError(f"Duyster aflevering {pid} heeft geen betrouwbare tracklijst")
    unique = []
    seen = set()
    for song in songs:
        if (not isinstance(song, (tuple, list)) or len(song) != 2
                or not all(isinstance(value, str) and value.strip() for value in song)):
            raise ValueError(f"Duyster aflevering {pid} bevat ongeldige metadata")
        key = song_key(song[0], song[1])
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append((song[0].strip(), song[1].strip(), key))
    if len(unique) < 5:
        raise ValueError(f"Duyster aflevering {pid} heeft te weinig unieke nummers")
    return unique


def _load_audit(path, newest, *, now=None):
    now = time.time() if now is None else float(now)
    if not Path(path).exists():
        return {
            "format": "v206-duyster-complete-episodes-v1",
            "next_pid": newest,
            "target_last_pid": newest,
            "verified_episodes": {},
            "total_recovered": 0,
            "complete": False,
        }
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(raw, dict)
            or raw.get("format") != "v206-duyster-complete-episodes-v1"
            or type(raw.get("next_pid")) is not int
            or not isinstance(raw.get("verified_episodes"), dict)
            or type(raw.get("target_last_pid")) is not int):
        raise ValueError("Ongeldige historische auditstatus; archief onveranderd")
    if raw.get("complete") is True:
        completed_at = raw.get("completed_at_utc")
        try:
            completed = datetime.fromisoformat(completed_at).timestamp()
        except (ValueError, TypeError):
            completed = 0
        if newest > raw["target_last_pid"] or now - completed >= RECHECK_AFTER_DAYS * 86400:
            raw = {
                "format": "v206-duyster-complete-episodes-v1",
                "next_pid": newest,
                "target_last_pid": newest,
                "verified_episodes": {},
                "total_recovered": raw.get("total_recovered", 0),
                "complete": False,
            }
    return raw


def audit_archief(
    *, archive=ARCHIVE, import_state=STATE, audit_state=AUDIT_STATE,
    fetch_page=get_episode, batch=DEFAULT_BATCH, pause=MIN_DELAY_SECONDS,
    sleep=time.sleep, now=None,
):
    if type(batch) is not int or not (1 <= batch <= MAX_BATCH):
        raise ValueError("Auditbatch moet 1..80 afleveringen zijn")
    if pause < 0:
        raise ValueError("Pauze mag niet negatief zijn")
    imported = read_state(import_state)
    newest = int(imported.get("last_imported_pid", 0) or 0)
    if newest < 1:
        raise ValueError("Geen betrouwbaar geïmporteerde Duyster-afleveringen")
    rows, lookup = read_archive(archive)
    audit = _load_audit(audit_state, newest, now=now)
    checked_now, recovered_now = 0, 0
    first_error = None

    # ALWAYS refresh the last three episodes; this catches recent gaps even if
    # the deep cursor takes many days to pass the whole archive.
    recent = [p for p in range(newest, max(0, newest - LATEST_PRIORITY_COUNT), -1)]
    # Historical audit starts at newest and descends to episode 1.
    deep = [p for p in range(audit["next_pid"], 0, -1)]
    targets = []
    for pid in recent + deep:
        if pid in targets:
            continue
        targets.append(pid)
        if len(targets) >= batch:
            break

    # Atomically publish a completed batch only. On a remote failure,
    # successfully verified earlier episodes can still be published safely;
    # cursor must remain at the failed episode (never skip it).
    for pid in targets:
        try:
            episode = fetch_page(pid)
            songs = _valid_episode(episode, pid)
        except Exception as exc:
            first_error = f"Aflevering {pid} niet bevestigd: {type(exc).__name__}: {exc}"
            print("⚠️ " + first_error)
            break
        added_for_episode = 0
        for artist, title, key in songs:
            if key not in lookup:
                lookup[key] = len(rows)
                rows.append({
                    "artist": artist, "title": title,
                    "first_seen_pid": str(pid), "seen_in": "1",
                })
                added_for_episode += 1
                recovered_now += 1
                print(f"♻️ Duyster hersteld uit aflevering {pid}: {artist} — {title}")
        key_digest = hashlib.sha256(
            "\n".join(sorted(key for _, _, key in songs)).encode("utf-8")
        ).hexdigest()
        audit["verified_episodes"][str(pid)] = {
            "source_tracks": len(songs),
            "recovered": added_for_episode,
            "source_sha256": key_digest,
            "checked_at_utc": _utc_now(),
        }
        checked_now += 1
        # The deep cursor never advances past an unchecked episode.
        if pid == audit["next_pid"]:
            audit["next_pid"] -= 1
        # Note: recent checks may be ahead of the deep cursor; the deep loop
        # deliberately re-verifies those when it reaches them.
        if pause and checked_now < len(targets):
            sleep(pause)

    audit["total_recovered"] = int(audit.get("total_recovered", 0)) + recovered_now
    audit["last_checked_at_utc"] = _utc_now()
    audit["last_batch_verified"] = checked_now
    audit["last_batch_recovered"] = recovered_now
    audit["last_error"] = first_error
    audit["complete"] = bool(
        audit["next_pid"] <= 0
        and all(str(pid) in audit["verified_episodes"] for pid in range(1, newest + 1))
        and first_error is None
    )
    if audit["complete"]:
        audit["completed_at_utc"] = _utc_now()

    if recovered_now:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        atomic_write(archive, buffer.getvalue())
    atomic_write(audit_state, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(f"📚 Duyster-audit: {checked_now} afleveringen vergeleken; "
          f"{recovered_now} ontbrekende nummers hersteld; "
          f"historische cursor {audit['next_pid']}; "
          f"volledig gecontroleerd={'JA' if audit['complete'] else 'NEE'}")
    if first_error:
        # The runner should remain visibly FAILED even if it was able to
        # persist a valid partial repair. The workflow uses always() to
        # commit the repaired data before concluding.
        raise RuntimeError(first_error)
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--pause", type=float, default=MIN_DELAY_SECONDS)
    args = parser.parse_args()
    audit_archief(batch=args.batch, pause=args.pause)


if __name__ == "__main__":
    main()
