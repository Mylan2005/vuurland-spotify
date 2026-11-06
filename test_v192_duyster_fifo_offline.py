"""v192: offline regresstests voor Duyster-archief in de gedeelde FIFO.

Geen netwerk, Spotify, statewijzigingen in de repository of externe pakketten.
"""
import ast
import csv
import os
import tempfile
from pathlib import Path
from duyster_archive_fifo import (
    enqueue_one, DUYSTER_ENQUEUE_INTERVAL_SECONDS,
    DUYSTER_MAX_PENDING, DUYSTER_MAX_TOTAL_QUEUE,
    _CURSOR, _NEXT,
)
from dark_edge_filter import dark_edge_reject_reason

ROOT = Path(__file__).resolve().parent
source = (ROOT / "vuurland_sync.py").read_text(encoding="utf-8")
module = ast.parse(source)
sync = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "sync")
sync_text = ast.get_source_segment(source, sync)

def key(artist, title):
    return f"{artist.strip().casefold()}|||{title.strip().casefold()}"

def allowed(artist, title):
    # Test simulatie van bestaande veiligheidsfilters.
    if "ich liebe" in title.casefold() or "das lied" in title.casefold():
        return False
    return dark_edge_reject_reason(artist, title) not in {
        "geblokkeerde dance-/EDM-, punk-/metalartiest of persoonlijke uitzondering",
        "expliciet uitgesloten opname",
    }

def no_playlist_match(artist, title, known):
    return key(artist, title) in known

def write_csv(root, name, rows, headers):
    with (Path(root) / name).open("w", encoding="utf-8", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(headers)
        out.writerows(rows)

with tempfile.TemporaryDirectory() as tmp:
    write_csv(tmp, "duyster_aflevering_833.csv", [
        ("Sigur Rós", "Von", "833", "2026-10-26"),
        ("Mogwai", "Remurdered", "833", "2026-10-26"),
        ("Blanco White", "Mano a Mano", "833", "2026-10-26"),
        ("Tomte", "Ich liebe dich", "833", "2026-10-26"),
        ("Avicii", "Levels", "833", "2026-10-26"),
    ], ("artist", "title", "pid", "episode_date"))
    write_csv(tmp, "duyster_archief_uniek.csv", [
        ("Mogwai", "Remurdered", 553, 11),  # dubbeltelling met 833
        ("Cocteau Twins", "Alice", 421, 3),
        ("Sigur Rós", "Von", 239, 5),  # dubbeltelling met 833
        ("Ólafur Arnalds", "Ljósið", 401, 2),
    ], ("artist", "title", "first_seen_pid", "seen_in"))

    cache = {"__playlist_keys": []}
    queue = [{"artist": "Editors", "title": "No Sound But the Wind", "source": "vuurland", "_v116_fifo_seq": 99}]
    original = dict(queue[0])
    base = 1000
    kwargs = dict(data_dir=tmp, key_func=key, allowed=allowed,
                  in_playlist=no_playlist_match)
    first = enqueue_one(cache, queue, set(), now=base, **kwargs)
    assert first == {"artist": "Sigur Rós", "title": "Von", "source": "duyster"}, first
    assert queue[0] == original
    assert len(queue) == 2
    assert cache[_NEXT] == base + 120
    assert enqueue_one(cache, queue, set(), now=base + 119, **kwargs) is None
    assert len(queue) == 2
    second = enqueue_one(cache, queue, set(), now=base + 120, **kwargs)
    assert second and second["artist"] == "Mogwai"
    assert queue[0] == original and len(queue) == 3
    third = enqueue_one(cache, queue, set(), now=base + 240, **kwargs)
    assert third and third["artist"] == "Blanco White"
    # De twee expliciet geweerde nummers mogen nooit door de achterdeur.
    fourth = enqueue_one(cache, queue, set(), now=base + 360, **kwargs)
    assert fourth and fourth["artist"] == "Cocteau Twins", fourth
    fifth = enqueue_one(cache, queue, set(), now=base + 480, **kwargs)
    assert fifth and fifth["artist"] == "Ólafur Arnalds"
    assert enqueue_one(cache, queue, set(), now=base + 600, **kwargs) is None
    assert len(queue) == 6
    assert all(x.get("source") == "duyster" for x in queue[1:])
    assert len({key(x["artist"], x["title"]) for x in queue}) == len(queue)

    # Na een restart blijft de 120s-rem behouden, geen dubbele injectie.
    assert enqueue_one(cache, queue, set(), now=base + 601, **kwargs) is None

    # Bestaande playlist, seen en queued items worden niet opnieuw ingepland.
    cache2 = {"__playlist_keys": [key("Sigur Rós", "Von")]}
    queue2 = [{"artist": "Mogwai", "title": "Remurdered", "source": "big_sonic_heaven"}]
    other = enqueue_one(cache2, queue2, {key("Blanco White", "Mano a Mano")},
                        now=base, **kwargs)
    assert other and other["artist"] == "Cocteau Twins", other

    # FIFO remmen als er al veel Duyster-nummers wachten.
    full_duyster = [{"artist": "X", "title": str(i), "source": "duyster"}
                    for i in range(DUYSTER_MAX_PENDING)]
    assert enqueue_one({}, full_duyster, set(), now=base, **kwargs) is None
    assert len(full_duyster) == DUYSTER_MAX_PENDING
    huge_queue = [{"artist": "X", "title": str(i), "source": "vuurland"}
                  for i in range(DUYSTER_MAX_TOTAL_QUEUE)]
    assert enqueue_one({}, huge_queue, set(), now=base, **kwargs) is None
    assert len(huge_queue) == DUYSTER_MAX_TOTAL_QUEUE

# De echte publicatie van 833 staat volledig en uniek in het archief.
with (ROOT / "duyster_aflevering_833.csv").open(encoding="utf-8", newline="") as handle:
    recent = list(csv.DictReader(handle))
assert len(recent) == 25
assert all(row["pid"] == "833" and row["episode_date"] == "2026-10-26" for row in recent)
with (ROOT / "duyster_archief_uniek.csv").open(encoding="utf-8", newline="") as handle:
    archive = list(csv.DictReader(handle))
assert len(archive) == 8557, len(archive)
all_keys = {key(row["artist"], row["title"]) for row in archive}
assert len(all_keys) == len(archive)
assert all(key(row["artist"], row["title"]) in all_keys for row in recent)

# Bestaande acht bronnen niet gewijzigd, Duyster alleen in FIFO laten.
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in source
assert 'for sid in RADIO_SOURCE_ORDER' in sync_text
assert "source_order = FIFO_SOURCE_ORDER" in sync_text
assert 'and str(item.get("source") or "vuurland").strip() in FIFO_SOURCE_ORDER' in sync_text
assert 'x.get("source") in FIFO_SOURCE_ORDER and' in sync_text
assert "duyster_added = enqueue_duyster_archive_one(" in sync_text
assert 'v116_stamp_fifo(live_queue, cache)' in sync_text
assert "Duyster permanently disabled" not in sync_text
assert "AUTOMATIC_PLAYLIST_INVENTORY_ENABLED = False" in source
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
assert DUYSTER_ENQUEUE_INTERVAL_SECONDS == 120

print("✅ Duyster-aflevering 833: 25 tracks, 8557 unieke archiefnummers; 120s-persistent FIFO.")
print("✅ Geen duplicaten, Duitse zang, EDM, oude queueverlies of extra Spotify-API-calls.")
