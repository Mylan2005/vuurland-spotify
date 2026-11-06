#!/usr/bin/env python3
"""v202: collect matcher failures from live state + recent Actions report artifacts.

READ ONLY: no Spotify API, no playlist writes, no automatic candidate approval.
Generates a stable GitHub issue body and downloadable machine-readable review.
"""
import argparse
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from v194_matcher_metadata import canonical_artist, artist_join_key
from vuurland_matcher_audit import audit


def norm(value):
    return " ".join(
        unicodedata.normalize("NFKC", str(value or "")).casefold().split()
    )


def same_artist(a, b):
    return bool(
        a and b
        and artist_join_key(canonical_artist(a))
        and artist_join_key(canonical_artist(a))
            == artist_join_key(canonical_artist(b))
    )


def candidates_from_log(value):
    """The run log displays 'Artist — Title | Artist — Title' previews."""
    results = []
    for entry in str(value or "").split(" | "):
        artist, separator, title = entry.partition(" — ")
        if separator and artist.strip() and title.strip():
            results.append((artist.strip(), title.strip()))
    return results


def classify(artist, title, previews):
    """Triage hint, NEVER proof of a valid or playable Spotify recording."""
    for found_artist, found_title in previews:
        if same_artist(artist, found_artist) and norm(title) == norm(found_title):
            return "gelijke_artiest_en_titel_nader_controleren"
    for found_artist, found_title in previews:
        if same_artist(artist, found_artist):
            if SequenceMatcher(None, norm(title), norm(found_title)).ratio() >= .78:
                return "mogelijke_titelvariant_handmatig_verifieren"
    return "geen_duidelijke_kandidaat"


def safe_cell(value):
    return str(value or "").replace("|", r"\|").replace("\r", " ").replace("\n", " ")[:140]


def summarize(cache, report_paths):
    historic = audit(cache)
    by_key = {}
    for row in historic:
        identity = (norm(row["artist"]), norm(row["title"]))
        if not all(identity):
            continue
        by_key[identity] = {
            "artist": row["artist"], "title": row["title"],
            "source": row["source"], "status": row["status"],
            "failed_searches": row["failed_searches"], "run_reports": 0,
            "queries": set(), "previews": set(),
        }

    used_reports = 0
    failures = []
    for path in sorted(set(Path(p) for p in report_paths)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                raise ValueError("geen matcher records-lijst")
            records = payload["records"]
            if not all(isinstance(x, dict) for x in records):
                raise ValueError("ongeldige recordvorm")
        except (OSError, UnicodeError, ValueError) as exc:
            failures.append({"bestand": path.name, "fout": str(exc)[:140]})
            continue
        used_reports += 1
        already_in_run = set()
        for record in records:
            artist = str(record.get("artiest") or "").strip()
            title = str(record.get("titel") or "").strip()
            if not artist or not title:
                continue
            # These log records are failures, not accepted Spotify recordings.
            ident = (norm(artist), norm(title))
            row = by_key.setdefault(ident, {
                "artist": artist, "title": title, "source": "",
                "status": "alleen_in_runrapport", "failed_searches": 0,
                "run_reports": 0, "queries": set(), "previews": set(),
            })
            if ident not in already_in_run:
                row["run_reports"] += 1
                already_in_run.add(ident)
            query = str(record.get("laatste_spotify_query") or "").strip()
            preview = str(record.get("afgewezen_kandidaten") or "").strip()
            if query:
                row["queries"].add(query[:250])
            if preview:
                row["previews"].update(candidates_from_log(preview))

    output = []
    categories = Counter()
    for row in by_key.values():
        verdict = classify(row["artist"], row["title"], row["previews"])
        categories[verdict] += 1
        output.append({
            "artist": row["artist"], "title": row["title"],
            "source": row["source"], "status": row["status"],
            "failed_searches": row["failed_searches"],
            "run_reports": row["run_reports"],
            "category": verdict,
            "queries": sorted(row["queries"]),
            "preview_candidates": [
                {"artist": a, "title": t} for a, t in sorted(row["previews"])
            ],
            "approved": False,
        })
    priority = {
        "gelijke_artiest_en_titel_nader_controleren": 0,
        "mogelijke_titelvariant_handmatig_verifieren": 1,
        "geen_duidelijke_kandidaat": 2,
    }
    output.sort(key=lambda x: (
        priority[x["category"]],
        -x["run_reports"], -x["failed_searches"],
        norm(x["artist"]), norm(x["title"]),
    ))
    return {
        "scope": ("persisted GitHub cache + available recent Actions matcher JSON artifacts; "
                  "expired/missing older artifacts are unavailable"),
        "spotify_requests": 0, "automatically_approved": 0,
        "historical_cache_records": len(historic),
        "read_report_files": used_reports, "invalid_report_files": failures,
        "unique_failures": len(output),
        "categories": dict(sorted(categories.items())),
        "records": output,
    }


def issue_body(report, maximum=25):
    lines = [
        "## Automatische matchertriage (alleen lezen)",
        "",
        "Dit issue wordt door een geplande GitHub Action bijgewerkt. "
        "**Geen Spotify-match is automatisch goedgekeurd.**",
        "Kandidaten uit de log kunnen live/remix/onbeschikbaar/verkeerd zijn. "
        "Elke echte matcherwijziging vereist bewijs, negatieve regressietests, CI en review.",
        "",
        f"- Historische meldingen uit actuele cache: **{report['historical_cache_records']}**",
        f"- Recent ingelezen Actions-rapporten: **{report['read_report_files']}**",
        f"- Unieke onopgeloste/historische vermeldingen: **{report['unique_failures']}**",
        "- Spotify API-aanvragen: **0**",
        "",
        "### Categorieën",
    ]
    for cat, count in report["categories"].items():
        lines.append(f"- {cat}: {count}")
    lines.extend([
        "", "### Te onderzoeken (maximaal {})".format(maximum), "",
        "| Radio-artiest | Radio-titel | Bron | Cache-status | Runs | Onderzoek |",
        "|---|---|---|---|---:|---|",
    ])
    for record in report["records"][:maximum]:
        lines.append("| " + " | ".join([
            safe_cell(record["artist"]), safe_cell(record["title"]),
            safe_cell(record["source"]), safe_cell(record["status"]),
            str(record["run_reports"]), safe_cell(record["category"]),
        ]) + " |")
    lines.extend([
        "", "### Beperkingen", "",
        "De lijst is een onderzoekslijst, geen catalogusbevestiging. "
        "Een oude cache-misser kan intussen opgelost zijn. "
        "De log vermeldt niet altijd de oorspronkelijke radiobron. "
        "GitHub Actions-artifacts zijn tijdelijk en dus niet de volledige historische log.",
        "De volledige evidence, zoekqueries en kandidaatpreviews staan in het "
        "downloadbare JSON-artifact van de workflow.",
        "",
        "### Volgende stap voor een codewijziging", "",
        "Bevestig bron-artiest, volledige titel, uitvoeringsversie, "
        "Spotify-beschikbaarheid en bestaande uitsluitingen; "
        "voeg dan positieve én negatieve offline regressietests toe. "
        "**Geen automatische PR-merges of algemene fuzzy versoepeling.**",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.cache.is_file():
        parser.error("cache ontbreekt; geen lege analyse verzinnen")
    cache = json.loads(args.cache.read_text(encoding="utf-8"))
    if not isinstance(cache, dict):
        parser.error("cache heeft geen JSON-objectvorm")
    paths = list(args.reports_dir.rglob("vuurland_matcher_rapport.json")) \
        if args.reports_dir.is_dir() else []
    report = summarize(cache, paths)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "matcher_automatische_analyse.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "matcher_automatische_issue.md").write_text(
        issue_body(report), encoding="utf-8"
    )
    print(f"✅ {report['unique_failures']} unieke meldingen, "
          f"{report['read_report_files']} runrapporten, "
          f"{len(report['invalid_report_files'])} onleesbare rapporten.")
    print("Geen Spotify-zoekopdrachten, automatisch toegevoegde nummers of cachemutaties.")


if __name__ == "__main__":
    main()
