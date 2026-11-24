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
GAP_MANIFEST = ROOT / "duyster_source_gaps.json"
LATEST_PRIORITY_COUNT = 3
DEFAULT_BATCH = 60
MAX_BATCH = 80
MIN_DELAY_SECONDS = 0.8
RECHECK_AFTER_DAYS = 30


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class DuysterEpisodeValidationError(ValueError):
    """Een aflevering faalt een expliciete bron-/metadata-validatiepoort."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _valid_episode(episode, pid):
    if episode is None:
        raise DuysterEpisodeValidationError(
            "source_missing_or_parse_mismatch",
            f"Duyster aflevering {pid}: bron gaf geen aflevering terug "
            "(404, lege pagina of parser kon het afleveringsnummer niet bevestigen)",
        )
    if not isinstance(episode, dict):
        raise DuysterEpisodeValidationError(
            "invalid_episode_payload",
            f"Duyster aflevering {pid}: bronantwoord is geen geldig object",
        )
    actual_pid = episode.get("pid")
    if actual_pid != pid:
        raise DuysterEpisodeValidationError(
            "wrong_episode_id",
            f"Duyster aflevering {pid}: bron bevestigde aflevering {actual_pid!r}",
        )
    songs = episode.get("songs")
    if not isinstance(songs, list):
        raise DuysterEpisodeValidationError(
            "missing_tracklist",
            f"Duyster aflevering {pid}: tracklijst ontbreekt of heeft verkeerd formaat",
        )
    if len(songs) < 5:
        raise DuysterEpisodeValidationError(
            "too_few_raw_tracks",
            f"Duyster aflevering {pid}: slechts {len(songs)} ruwe tracks; minimaal 5 vereist",
        )
    unique = []
    seen = set()
    for index, song in enumerate(songs, start=1):
        if (not isinstance(song, (tuple, list)) or len(song) != 2
                or not all(isinstance(value, str) and value.strip() for value in song)):
            raise DuysterEpisodeValidationError(
                "invalid_track_metadata",
                f"Duyster aflevering {pid}: ongeldige artiest/titel op trackpositie {index}",
            )
        key = song_key(song[0], song[1])
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append((song[0].strip(), song[1].strip(), key))
    if len(unique) < 5:
        raise DuysterEpisodeValidationError(
            "too_few_unique_tracks",
            f"Duyster aflevering {pid}: {len(unique)} unieke tracks uit {len(songs)} "
            "ruwe vermeldingen; minimaal 5 vereist",
        )
    return unique




def _load_source_gap_manifest(path):
    """Load explicit, evidence-backed source gaps; never infer or auto-skip IDs."""
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(raw, dict)
            or raw.get("format") != "v206-duyster-source-gaps-v1"
            or not isinstance(raw.get("gaps"), list)):
        raise ValueError("Ongeldig Duyster-brongatenmanifest; cursor blijft onveranderd")
    gaps = {}
    for entry in raw["gaps"]:
        if not isinstance(entry, dict) or type(entry.get("pid")) is not int or entry["pid"] < 1:
            raise ValueError("Ongeldige pid in Duyster-brongatenmanifest")
        if entry.get("status") != "official_site_empty_record":
            raise ValueError(f"Niet-toegestane bronuitzondering voor pid {entry.get('pid')}")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            raise ValueError(f"Geen onderbouwing voor bronuitzondering pid {entry['pid']}")
        urls = entry.get("evidence_urls")
        if (not isinstance(urls, list) or not urls
                or not all(isinstance(url, str) and url.startswith("https://") for url in urls)):
            raise ValueError(f"Geen officiële bewijs-URL's voor bronuitzondering pid {entry['pid']}")
        if entry["pid"] in gaps:
            raise ValueError(f"Dubbele bronuitzondering voor pid {entry['pid']}")
        gaps[entry["pid"]] = entry
    return gaps

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
    sleep=time.sleep, now=None, gap_manifest=GAP_MANIFEST,
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
    known_source_gaps = _load_source_gap_manifest(gap_manifest)
    if not isinstance(audit.get("source_gaps", {}), dict):
        raise ValueError("Ongeldige opgeslagen bron-gaten; archief onveranderd")
    audit.setdefault("source_gaps", {})
    checked_now, recovered_now = 0, 0
    source_gaps_now, processed_now = 0, 0
    first_error = None
    error_pid = None
    error_code = None

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
            error_code = getattr(exc, "code", "source_fetch_error")
            gap = known_source_gaps.get(pid)
            if gap is not None and error_code == "parser_pid_not_confirmed":
                # This exact ID is independently documented as an empty
                # official-site placeholder. Record a gap, not a verified show.
                audit["source_gaps"][str(pid)] = {
                    "status": gap["status"],
                    "reason": gap["reason"],
                    "evidence_urls": gap["evidence_urls"],
                    "checked_at_utc": _utc_now(),
                    "source_error_code": error_code,
                }
                if pid == audit["next_pid"]:
                    audit["next_pid"] -= 1
                source_gaps_now += 1
                processed_now += 1
                print(f"ℹ️ Duyster pid {pid}: expliciet geregistreerde lege bronpagina; "
                      "niet als aflevering geverifieerd.")
                if pause and processed_now < len(targets):
                    sleep(pause)
                continue
            first_error = f"Aflevering {pid} niet bevestigd [{error_code}]: {type(exc).__name__}: {exc}"
            error_pid = pid
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
        processed_now += 1
        # The deep cursor never advances past an unchecked episode.
        if pid == audit["next_pid"]:
            audit["next_pid"] -= 1
        # Note: recent checks may be ahead of the deep cursor; the deep loop
        # deliberately re-verifies those when it reaches them.
        if pause and processed_now < len(targets):
            sleep(pause)

    audit["total_recovered"] = int(audit.get("total_recovered", 0)) + recovered_now
    audit["last_checked_at_utc"] = _utc_now()
    audit["last_batch_verified"] = checked_now
    audit["last_batch_source_gaps"] = source_gaps_now
    audit["last_batch_processed"] = processed_now
    audit["last_batch_recovered"] = recovered_now
    audit["last_error"] = first_error
    audit["last_error_pid"] = error_pid
    audit["last_error_code"] = error_code
    resolved = set(audit["verified_episodes"]) | set(audit["source_gaps"])
    audit["scan_finished"] = bool(
        audit["next_pid"] <= 0
        and all(str(pid) in resolved for pid in range(1, newest + 1))
    )
    audit["complete"] = bool(
        audit["scan_finished"] and not audit["source_gaps"] and first_error is None
    )
    audit["complete_with_known_gaps"] = bool(
        audit["scan_finished"] and audit["source_gaps"] and first_error is None
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
          f"bekende lege bronpagina's={len(audit['source_gaps'])}; "
          f"scan afgerond={'JA' if audit['scan_finished'] else 'NEE'}; "
          f"volledig bron-gecontroleerd={'JA' if audit['complete'] else 'NEE'}")
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
    audit_archief(
        batch=args.batch,
        pause=args.pause,
        fetch_page=lambda pid: get_episode(pid, strict=True),
    )


if __name__ == "__main__":
    main()
