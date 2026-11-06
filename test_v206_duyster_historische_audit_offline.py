"""v206: regressies: alle brontracks, geen skip van gemiste afleveringen.

Alles offline: GEEN Spotify API, geen Duyster netwerk, geen FIFO/state mutatie.
"""
import csv
import json
import tempfile
from pathlib import Path

from duyster_historische_audit import audit_archief


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    archive = root / "duyster_archief_uniek.csv"
    imported = root / "duyster_archief_import_state.json"
    audit_state = root / "audit.json"
    imported.write_text('{"next_pid":834,"last_imported_pid":833}', encoding="utf-8")
    archive.write_text(
        "artist,title,first_seen_pid,seen_in\n"
        "CLARA MANN,Fortuna,833,1\n"
        "Pinback,Penelope,100,5\n",
        encoding="utf-8",
    )
    p832 = [
        ("Pinback", "Penelope"),
        ("MARY IN THE JUNKYARD", "Jane"),
        ("LINUS & BONNIE 'PRINCE' BILLY", "And God Saw"),
        ("I'M THE HUG", "Mom, I Tried"),
        ("Bonobo", "Fire on the Water (feat. Arooj Aftab)"),
        ("Dead Calm", "Grow"),
        ("Helen", "Canyon"),
        ("Goldmund", "Safe to the World"),
        ("Ida", "Truxtun Park"),
    ]
    calls = []
    def fetch(pid):
        calls.append(pid)
        if pid == 833:
            return {"pid": 833, "songs": [("CLARA MANN", "Fortuna")] +
                    [(f"Other {j}", f"Track {j}") for j in range(4)]}
        if pid == 832:
            return {"pid": 832, "songs": p832}
        return {"pid": pid, "songs": [(f"Other {pid}-{j}", f"Track {j}") for j in range(5)]}

    result = audit_archief(
        archive=archive, import_state=imported, audit_state=audit_state,
        fetch_page=fetch, batch=4, pause=0,
    )
    assert calls == [833, 832, 831, 830], calls
    assert result["next_pid"] == 829 and result["complete"] is False
    assert result["last_batch_recovered"] >= 8
    with archive.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert any(row["artist"] == "MARY IN THE JUNKYARD" and row["title"] == "Jane" for row in rows)
    assert any(row["artist"] == "LINUS & BONNIE 'PRINCE' BILLY" and row["title"] == "And God Saw" for row in rows)
    assert [row["seen_in"] for row in rows if row["artist"] == "Pinback"] == ["5"]
    assert json.loads(imported.read_text()) == {"next_pid": 834, "last_imported_pid": 833}

    # Recheck recent episodes, do not append duplicates.
    old = archive.read_bytes()
    audit_archief(
        archive=archive, import_state=imported, audit_state=audit_state,
        fetch_page=fetch, batch=3, pause=0,
    )
    assert archive.read_bytes() == old, "Hercontrole mag geen dubbels creëren"
    assert json.loads(audit_state.read_text())["next_pid"] == 829

    # A missing episode must NEVER be declared verified or skipped.
    def broken(pid):
        if pid == 828:
            return None
        return fetch(pid)
    try:
        audit_archief(
            archive=archive, import_state=imported, audit_state=audit_state,
            fetch_page=broken, batch=5, pause=0,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Incomplete source must fail visibly")
    after = json.loads(audit_state.read_text())
    assert after["next_pid"] == 828, after["next_pid"]
    assert after["complete"] is False and after["last_error"]
    assert "828" not in after["verified_episodes"]

    # Even an unreadable JSON audit file must not reset an active scan.
    audit_state.write_text("{garbled", encoding="utf-8")
    before = archive.read_bytes()
    try:
        audit_archief(
            archive=archive, import_state=imported, audit_state=audit_state,
            fetch_page=fetch, batch=3, pause=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Corrupt saved audit was silently reset")
    assert archive.read_bytes() == before

    # No complete claim until every source episode has been verified.
    result = json.loads('{"format":"v206-duyster-complete-episodes-v1",'
                        '"next_pid":1,"target_last_pid":833,'
                        '"verified_episodes":{},"total_recovered":0,"complete":false}')
    audit_state.write_text(json.dumps(result), encoding="utf-8")
    done = audit_archief(
        archive=archive, import_state=imported, audit_state=audit_state,
        fetch_page=fetch, batch=5, pause=0,
    )
    assert done["next_pid"] == 0 and done["complete"] is False
    assert "1" in done["verified_episodes"]

print("✅ v206: recente bronmissers, historische cursor, geen dubbele items of vals volledige audit.")
