#!/usr/bin/env python3
"""v257: read-only quality snapshot for Vuurland's 17 live sources and Duyster.

Never imports the sync engine, accesses Spotify, or writes to existing state.
Queue is a CURRENT snapshot, not historical intake or Spotify match statistics.
"""
import argparse
import collections
import datetime as dt
import json
from pathlib import Path

LIVE_SOURCES = (
    "vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled",
    "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge",
    "dkfm_shoegaze", "dkfm_classic", "egofm_rnb", "egofm_chillout",
    "dj_neihtul", "gri_balkon", "ignoreradio_shoegaze",
    "radio_britannia", "wbru",
)
LABELS = {
    "vuurland": "Studio Brussel Vuurland", "mellow_mix": "Mellow Mix",
    "big_sonic_heaven": "Big Sonic Heaven", "radio_x_chilled": "Radio X Chilled",
    "dreampop_radio": "Dreampop Radio", "indie_select": "Indie Select",
    "dkfm_edge": "DKFM Edge", "dark_edge": "Dark Edge",
    "dkfm_shoegaze": "DKFM Shoegaze", "dkfm_classic": "DKFM Classic",
    "egofm_rnb": "egoFM R&B", "egofm_chillout": "egoFM Chillout",
    "dj_neihtul": "DJ Neihtul", "gri_balkon": "GRI Balkon",
    "ignoreradio_shoegaze": "IgnoreRadio Shoegaze",
    "radio_britannia": "Radio Britannia", "wbru": "WBRU",
    "duyster": "Duyster (archief)",
}


def key(row):
    artist, title = row.get("artist"), row.get("title")
    if not isinstance(artist, str) or not isinstance(title, str):
        return None
    a, t = artist.strip().casefold(), title.strip().casefold()
    return (a, t) if a and t else None


def build_report(rows, *, timestamp=None):
    if not isinstance(rows, list):
        raise ValueError("Queue moet een JSON-lijst zijn")
    groups = collections.defaultdict(list)
    unknown = collections.Counter()
    invalid_rows = 0
    seqs = []
    for row in rows:
        if not isinstance(row, dict):
            invalid_rows += 1
            continue
        source = row.get("source")
        if not isinstance(source, str) or source not in LABELS:
            unknown[str(source)] += 1
            continue
        groups[source].append(row)
        seq = row.get("_v116_fifo_seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            seqs.append(seq)
    source_rows = []
    for source in (*LIVE_SOURCES, "duyster"):
        items = groups[source]
        valid = [v for v in (key(x) for x in items) if v is not None]
        distinct = len(set(valid))
        source_rows.append({
            "source": source, "name": LABELS[source], "pending": len(items),
            "unique_pending_titles": distinct,
            "duplicate_pending_titles": len(valid) - distinct,
            "invalid_metadata": len(items) - len(valid),
            "type": "archive" if source == "duyster" else "live",
        })
    warnings = []
    if unknown:
        warnings.append("Onbekende bronnen in de wachtrij: " + ", ".join(sorted(unknown)))
    if invalid_rows:
        warnings.append(f"{invalid_rows} ongeldige wachtrijregels")
    if len(seqs) != len(rows) - invalid_rows - sum(unknown.values()):
        warnings.append("Ontbrekende of ongeldige FIFO-volgnummers")
    if len(seqs) != len(set(seqs)):
        warnings.append("Dubbele FIFO-volgnummers")
    return {
        "version": 257,
        "generated_utc": timestamp or dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshot_only": True,
        "total_pending": len(rows),
        "sources": source_rows,
        "unknown_sources": dict(unknown),
        "warnings": warnings,
        "unavailable_historical_metrics": [
            "ingest_count", "spotify_search_count", "spotify_match_success",
            "added_to_spotify", "rejected_by_reason", "last_successful_poll",
        ],
    }


def markdown(report):
    lines = [
        "# Vuurland v257 — bronnenkwaliteit",
        "",
        f"Momentopname (UTC): {report['generated_utc']}",
        "",
        "**Alleen-lezen.** Dit rapport toont de huidige wachtrij, niet alle ooit "
        "ontvangen nummers en niet het aantal geslaagde Spotify-toevoegingen.",
        "",
        f"**Totaal in wachtrij:** {report['total_pending']}",
        "",
        "| Bron | Type | Wachtend | Unieke titels | Dubbelen | Ongeldige metadata |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in report["sources"]:
        lines.append(
            f"| {row['name']} | {row['type']} | {row['pending']} | "
            f"{row['unique_pending_titles']} | {row['duplicate_pending_titles']} | "
            f"{row['invalid_metadata']} |"
        )
    lines.extend(["", "## Signalen", ""])
    if report["warnings"]:
        lines.extend(f"- ⚠️ {w}" for w in report["warnings"])
    else:
        lines.append("- Geen wachtrijstructuurproblemen vastgesteld.")
    lines.extend([
        "", "## Niet uit deze snapshot af te leiden", "",
        "Historische instroom, geweigerde nummers en redenen, Spotify-zoekbeurten, "
        "matchsuccessen, effectieve Spotify-toevoegingen en laatste succesvolle "
        "broncontrole zijn niet betrouwbaar te reconstrueren uit alleen deze JSON.",
        "Voor die cijfers zijn afzonderlijk bewaarde gebeurtenissen of complete "
        "runnerlogs nodig. Nul in de wachtrij is **geen bewijs** van een defecte bron.",
        "",
        "De rapportage wijzigt geen filters, beurtrol, FIFO, playlists, cache of Spotify-budget.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="vuurland_live_queue.json")
    parser.add_argument("--out-dir", default="bronnenkwaliteit_v257")
    args = parser.parse_args()
    rows = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    report = build_report(rows)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bronnenkwaliteit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "bronnenkwaliteit.md").write_text(markdown(report), encoding="utf-8")
    print(f"v257: read-only rapport, {report['total_pending']} wachtende nummers")


if __name__ == "__main__":
    main()
