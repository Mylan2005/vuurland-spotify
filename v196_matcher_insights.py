#!/usr/bin/env python3
"""v196: read-only overview of ALL misses still recorded in current cache.

No network, no Spotify calls, no queue writes, no automatic matching.
This is a snapshot of persisted state, not a claim that Spotify lacks a track.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from vuurland_matcher_audit import audit


def summarize(cache, *, now):
    rows = audit(cache)
    parked = cache.get("__v51_radio_unmatched", {}) or {}
    failed = cache.get("__v47_failed_tracks", {}) or {}
    latest = cache.get("__v195_radio_replay_last_by_key", {}) or {}
    total_queue = cache.get("__v116_fifo_next_sequence")
    by_source = Counter()
    by_status = Counter()
    detail = []
    for row in rows:
        key = row["key"]
        entry = parked.get(key) if isinstance(parked, dict) else None
        source = row["source"] or "bron_onbekend"
        by_source[source] += 1
        by_status[row["status"]] += 1
        retry_state = "niet_geparkeerd"
        if isinstance(entry, dict):
            stamp = entry.get("failed_at")
            last = latest.get(key) if isinstance(latest, dict) else None
            try:
                stamp = float(stamp)
                last = float(last) if last is not None else None
            except (TypeError, ValueError, OverflowError):
                stamp = None
                last = None
            if stamp is None or stamp <= 0 or stamp > now:
                retry_state = "tijdstip_onbekend"
            elif now - stamp < 30 * 86400:
                retry_state = "wachttijd_30_dagen"
            elif last is not None and (last <= 0 or last > now or now - last < 30 * 86400):
                retry_state = "recent_herprobeerd"
            else:
                # v195 also requires a new radio play, other dedupe/filters and
                # a global cooldown. Never advertise eligibility as guaranteed.
                retry_state = "wacht_op_nieuwe_radio_uitzending_en_controles"
        detail.append({
            **row, "herkansingsstatus": retry_state,
            "veilig_automatisch_gevonden": False,
        })
    return {
        "gemaakt_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "bereik": "bewaarde cache; geen historische GitHub-artifacts of live Spotify-controle",
        "totaal_unieke_meldingen": len(detail),
        "per_status": dict(sorted(by_status.items())),
        "per_bron": dict(sorted(by_source.items())),
        "historische_fifo_volgnummer_hint": total_queue,
        "nummers": detail,
    }


def markdown(report):
    lines = [
        "# Vuurland v196 — historische matcherinzichten", "",
        "Alleen-lezen analyse van bewaarde missers; geen goedgekeurde Spotify-matches.",
        "Oudere GitHub-runrapporten zijn NIET automatisch inbegrepen.", "",
        f"**Unieke meldingen:** {report['totaal_unieke_meldingen']}", "",
        "## Statusverdeling", "",
    ]
    for name, count in report["per_status"].items():
        lines.append(f"- {name}: {count}")
    lines += ["", "## Bronnen", ""]
    for name, count in report["per_bron"].items():
        lines.append(f"- {name}: {count}")
    lines += ["", "## Nummers", "",
              "| Bron | Artiest | Titel | Status | v195-herkansing |",
              "|---|---|---|---|---|"]
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")[:180]
    for item in report["nummers"]:
        lines.append("| " + " | ".join(cell(item[name]) for name in
            ("source", "artist", "title", "status", "herkansingsstatus")) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    cache_file = args.data_dir / ".vuurland_spotify_cache.json"
    if not cache_file.exists():
        raise SystemExit("Cache ontbreekt; geen gegevens verzinnen.")
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    report = summarize(cache, now=datetime.now(timezone.utc).timestamp())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vuurland_v196_matcherinzichten.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.out_dir / "vuurland_v196_matcherinzichten.md").write_text(
        markdown(report), encoding="utf-8"
    )
    print("Matcherinzichten: {} unieke meldingen (offline; geen Spotify-calls).".format(
        report["totaal_unieke_meldingen"]))


if __name__ == "__main__":
    main()
