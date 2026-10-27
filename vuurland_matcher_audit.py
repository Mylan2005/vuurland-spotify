#!/usr/bin/env python3
"""Complete, read-only historical matcher audit. Zero Spotify/API calls."""
import argparse
import json
from pathlib import Path


def audit(cache):
    if not isinstance(cache, dict):
        raise ValueError("Spotify-cache moet een JSON-object zijn")
    failed = cache.get("__v51_radio_failed_searches", {}) or {}
    parked = cache.get("__v51_radio_unmatched", {}) or {}
    retry = cache.get("__v47_failed_tracks", {}) or {}
    confirmed = cache.get("__v82_confirmed_catalog", {}) or {}
    keys = cache.get("__playlist_keys", []) or []
    if not all(isinstance(x, dict) for x in (failed, parked, retry, confirmed)):
        raise ValueError("Onverwacht formaat van historische matchergegevens")
    if not isinstance(keys, list):
        raise ValueError("Onverwacht formaat van playlist-cache")
    existing = set(x for x in keys if isinstance(x, str))
    rows = []
    for key in sorted(set(failed) | set(parked) | set(retry)):
        if not isinstance(key, str):
            continue
        entry = parked.get(key) or retry.get(key) or {}
        if not isinstance(entry, dict):
            entry = {}
        try:
            count = max(0, int(failed.get(key, 0) or 0))
        except (ValueError, TypeError):
            count = 0
        artist, _, title = key.partition("|||")
        status = ("reeds_in_playlist_cache" if key in existing else
                  "catalogushint_te_verifieren" if key in confirmed else
                  "geparkeerd" if key in parked else
                  "wacht_op_nieuwe_poging" if key in retry else
                  "historische_misser")
        rows.append({
            "artist": str(entry.get("artist") or artist),
            "title": str(entry.get("title") or title),
            "source": str(entry.get("source") or ""),
            "failed_searches": count,
            "status": status,
            "key": key,
        })
    rows.sort(key=lambda x: (-x["failed_searches"], x["artist"].casefold(), x["title"].casefold()))
    return rows


def markdown(rows):
    lines = [
        "# Vuurland — volledige matcher-audit", "",
        "Historische mislukkingen, wachtende retries en geparkeerde nummers.",
        "Geen live Spotify-cataloguscontrole. Niets automatisch koppelen of toevoegen.", "",
        f"**Totaal verschillende vermeldingen:** {len(rows)}", "",
        "| Zoekpogingen | Status | Bron | Artiest — Titel |",
        "|---:|---|---|---|",
    ]
    for row in rows:
        def cell(v):
            return str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ")[:250]
        lines.append("| {} | {} | {} | {} |".format(
            row["failed_searches"], cell(row["status"]), cell(row["source"]),
            cell(row["artist"] + " — " + row["title"])))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    cache_file = args.data_dir / ".vuurland_spotify_cache.json"
    if not cache_file.exists():
        raise SystemExit("Cache ontbreekt; niets verzonnen en geen rapport gegenereerd")
    rows = audit(json.loads(cache_file.read_text(encoding="utf-8")))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vuurland_matcher_audit.md").write_text(markdown(rows), encoding="utf-8")
    (args.out_dir / "vuurland_matcher_audit.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Volledige matcher-audit: {len(rows)} historische vermeldingen; geen Spotify-verzoeken")


if __name__ == "__main__":
    main()
