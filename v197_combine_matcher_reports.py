#!/usr/bin/env python3
"""v197: combine many historical matcher report CSV/JSON files offline.

Read-only against inputs. No Spotify API, no fuzzy approval, no queue mutations.
Use --input-dir with downloaded GitHub matcher report artifacts.
"""
import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

COLUMNS = ("artiest", "titel", "bron", "status", "laatste_spotify_query",
           "afgewezen_kandidaten", "mislukte_zoekacties_in_log")
OUTPUT_FIELDS = ("artiest", "titel", "meldingen", "rapporten", "bronnen",
                 "statussen", "laatste_zoekqueries", "afgewezen_kandidaten")


def identity(artist, title):
    """Only case/Unicode/spacing equality; not fuzzy title or version matching."""
    def normalized(value):
        return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())
    return normalized(artist), normalized(title)


def _records(path):
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    if not isinstance(payload, list):
        raise ValueError("Geen records-lijst")
    return payload


def aggregate(paths):
    merged = {}
    errors = []
    processed = 0
    for path in sorted(set(Path(p) for p in paths)):
        try:
            records = _records(path)
            if not all(isinstance(x, dict) for x in records):
                raise ValueError("Rapport bevat geen geldige rijen")
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            errors.append({"bestand": path.name, "fout": str(exc)[:250]})
            continue
        processed += 1
        # CSV and JSON of the same run may have identical records. Report-level
        # duplicates are not automatically counted as different radio plays.
        within_file = set()
        for row in records:
            artist = str(row.get("artiest") or row.get("artist") or "").strip()
            title = str(row.get("titel") or row.get("title") or "").strip()
            if not artist or not title:
                continue
            key = identity(artist, title)
            if not all(key):
                continue
            record = merged.setdefault(key, {
                "artiest": artist, "titel": title, "meldingen": 0,
                "_files": set(), "_sources": set(), "_statuses": set(),
                "_queries": set(), "_candidates": set(),
            })
            record["_files"].add(str(path))
            for field, dest in (
                ("bron", "_sources"), ("source", "_sources"),
                ("status", "_statuses"),
                ("laatste_spotify_query", "_queries"),
                ("afgewezen_kandidaten", "_candidates"),
            ):
                value = str(row.get(field) or "").strip()
                if value and value != "Niet afzonderlijk gelogd":
                    record[dest].add(value[:500])
            # Count each track once per report, not per raw repeated log line.
            if key not in within_file:
                record["meldingen"] += 1
                within_file.add(key)
    rows = []
    for entry in merged.values():
        rows.append({
            "artiest": entry["artiest"],
            "titel": entry["titel"],
            "meldingen": entry["meldingen"],
            "rapporten": len(entry["_files"]),
            "bronnen": "; ".join(sorted(entry["_sources"])),
            "statussen": "; ".join(sorted(entry["_statuses"])),
            "laatste_zoekqueries": "; ".join(sorted(entry["_queries"])),
            "afgewezen_kandidaten": "; ".join(sorted(entry["_candidates"])),
        })
    rows.sort(key=lambda x: (-x["rapporten"], x["artiest"].casefold(), x["titel"].casefold()))
    return {"gelezen_bestanden": processed, "fouten": errors,
            "unieke_nummers": len(rows), "nummers": rows,
            "betekenis": "Onderzoeksrapport: kandidaten zijn NIET goedgekeurd voor Spotify."}


def markdown(report):
    lines = [
        "# Vuurland v197 — gecombineerde matcher-rapporten", "",
        "Alleen-lezen overzicht; geen Spotify-queries, geen automatische matches.",
        "Verschillende bestanden van dezelfde run kunnen dubbeltellen; gebruik bij voorkeur één formaat per run.",
        "", f"**Gelezen rapporten:** {report['gelezen_bestanden']}",
        f"**Unieke artiest/titel-combinaties:** {report['unieke_nummers']}", "",
        "| Rapporten | Artiest | Titel | Status |",
        "|---:|---|---|---|",
    ]
    def safe(v):
        return re.sub(r"[\r\n]+", " ", str(v)).replace("|", "\\|")[:180]
    for row in report["nummers"]:
        lines.append(f"| {row['rapporten']} | {safe(row['artiest'])} | {safe(row['titel'])} | {safe(row['statussen'])} |")
    if report["fouten"]:
        lines.extend(["", "## Overgeslagen bestanden"])
        for err in report["fouten"]:
            lines.append(f"- {safe(err['bestand'])}: {safe(err['fout'])}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.input_dir.is_dir():
        parser.error("input-dir bestaat niet")
    paths = [p for p in args.input_dir.rglob("*") if p.is_file()
             and p.suffix.lower() in (".csv", ".json")
             and "matcher" in p.name.casefold()
             and ("rapport" in p.name.casefold() or "report" in p.name.casefold())]
    report = aggregate(paths)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "v197_gecombineerd.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "v197_gecombineerd.md").write_text(markdown(report), encoding="utf-8")
    with (args.out_dir / "v197_gecombineerd.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(report["nummers"])
    print(f"✅ {report['gelezen_bestanden']} rapporten verwerkt, {report['unieke_nummers']} unieke nummers, "
          f"{len(report['fouten'])} overgeslagen bestanden. Geen Spotify-calls.")


if __name__ == "__main__":
    main()
