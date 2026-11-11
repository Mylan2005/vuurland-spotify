"""Daily matcher bot: propose only exact, reproducible third-search queries.

Consumes the existing v202 triage JSON. Never approves a Spotify match.
No HTTP requests, no Spotify calls, no queue/playlist/cache mutations.
Outputs a reviewable JSON diff; GitHub workflow opens a PR for any changes.
"""
import argparse
import json
import re
from pathlib import Path

from v194_matcher_metadata import artist_join_key, canonical_artist
from v223_report_search_hints import _ALLOWED_SOURCES, _key, load_hints

# Do not auto-propose source strings containing ambiguous format/version hints.
# Quoted phrases are safe search hints, but their apparent candidate metadata
# is not enough to prove the recorded version.
_UNSAFE = re.compile(
    r"\b(live|acoustic|unplugged|remix|mix|edit|demo|cover|radio edit|"
    r"instrumental|extended|session|bootleg|remaster(?:ed)?)\b",
    re.IGNORECASE,
)


def suggested_hints(report, current, limit=15):
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        raise ValueError("Geen geldige matcheranalyse")
    existing = {(row["artist"].casefold().strip(), row["title"].casefold().strip())
                for row in current["hints"]}
    suggestions = []
    for row in report["records"]:
        if not isinstance(row, dict):
            continue
        artist, title = row.get("artist"), row.get("title")
        source = row.get("source")
        count = row.get("run_reports")
        if (not isinstance(artist, str) or not isinstance(title, str)
                or not artist.strip() or not title.strip()
                or source not in _ALLOWED_SOURCES
                or not isinstance(count, int) or isinstance(count, bool) or count < 2
                or len(artist) > 120 or len(title) > 180
                or re.search(r'[\r\n"\\]', artist + title)
                or _UNSAFE.search(title)
                or row.get("category") != "gelijke_artiest_en_titel_nader_controleren"
                or (artist.casefold().strip(), title.casefold().strip()) in existing):
            continue
        previews = row.get("preview_candidates")
        if not isinstance(previews, list):
            continue
        # An exact artist + title in a preview is only a search hint,
        # NOT proof that Spotify returned the right album or version.
        if not any(
            isinstance(p, dict)
            and isinstance(p.get("artist"), str)
            and isinstance(p.get("title"), str)
            and artist_join_key(canonical_artist(artist))
            == artist_join_key(canonical_artist(p["artist"]))
            and bool(artist_join_key(canonical_artist(artist)))
            and _key(title) == _key(p["title"])
            for p in previews
        ):
            continue
        entry = {
            "artist": artist.strip(), "title": title.strip(),
            "source": source, "independent_reports": count,
        }
        suggestions.append(entry)
        existing.add((artist.casefold().strip(), title.casefold().strip()))
        if len(suggestions) >= limit:
            break
    return suggestions


def build(report, previous):
    current = json.loads(Path(previous).read_text(encoding="utf-8"))
    if current.get("schema_version") != 1:
        raise ValueError("Unsupported matcher hint schema")
    load_hints(previous)  # validate existing definitions; no silent corruption
    additions = suggested_hints(report, current)
    return {"schema_version": 1, "hints": current["hints"] + additions}, additions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.analysis.read_text(encoding="utf-8"))
    proposed, additions = build(report, args.current)
    args.output.write_text(
        json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Matcherbot — voorstel van exacte zoekhints",
        "",
        f"**{len(additions)} nieuwe zoekhint(s)** uit minstens twee "
        "onafhankelijke runrapporten en een exacte kandidaatpreview.",
        "",
        "Deze wijzigingen beperken zich tot de bestaande derde zoekpoging. "
        "**Geen match wordt automatisch goedgekeurd.** "
        "Alle uitvoerings-, artiest-, Spotify-markt-, ISRC- en duplicaatcontroles "
        "blijven ongewijzigd. Geen extra Spotify Search.",
        "",
        "De bronrapporten zijn diagnostisch; vóór een merge moet iemand "
        "de kandidaat/uitvoering beoordelen. "
        "Bij twijfel: PR sluiten zonder merge.",
        "",
    ]
    for row in additions:
        lines.append(f"- {row['artist']} — {row['title']} "
                     f"({row['source']}, {row['independent_reports']} rapporten)")
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Matcherbot: {len(additions)} begrensde derde-zoekhints voorgesteld.")


if __name__ == "__main__":
    main()
