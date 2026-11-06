"""v198: paired CSV/JSON exports do not inflate matcher report counts."""
import csv
import json
import tempfile
from pathlib import Path
from v197_combine_matcher_reports import aggregate, markdown

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    folder = root / "run_42"
    folder.mkdir()
    entries = [{"artiest": "Artist", "titel": "One", "bron": "vuurland", "status": "Onzeker"}]
    (folder / "vuurland_matcher_rapport.json").write_text(
        json.dumps({"records": entries}), encoding="utf-8")
    with (folder / "vuurland_matcher_rapport.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=entries[0])
        writer.writeheader()
        writer.writerows(entries)
    another = root / "run_43"
    another.mkdir()
    (another / "vuurland_matcher_rapport.json").write_text(
        json.dumps({"records": entries + [
            {"artiest": "Other", "titel": "Song (Live)", "bron": "indie_select",
             "status": "Geparkeerd"}]}), encoding="utf-8")
    report = aggregate(sorted(root.rglob("vuurland_matcher_rapport.*")))
    assert report["gelezen_bestanden"] == 2, report
    assert len(report["dubbele_exports_overgeslagen"]) == 1, report
    assert report["unieke_nummers"] == 2, report
    assert report["nummers"][0]["rapporten"] == 2
    assert report["statusverdeling_unieke_nummers"] == {"Geparkeerd": 1, "Onzeker": 1}
    assert report["bronverdeling_unieke_nummers"] == {"indie_select": 1, "vuurland": 1}
    assert "Meest voorkomende statussen" in markdown(report)
    assert "Overgeslagen dubbele exports" in markdown(report)
print("✅ v198: paired reports deduplicated and safe summary generated.")
