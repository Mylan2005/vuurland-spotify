"""v192: offline regresstests voor Duyster-archief in de gedeelde FIFO.

Geen netwerk, Spotify, statewijzigingen in de repository of externe pakketten.
"""
import ast
import csv
import os
import random
import tempfile
from pathlib import Path
from duyster_archive_fifo import (
    enqueue_one, DUYSTER_ENQUEUE_INTERVAL_SECONDS,
    DUYSTER_MAX_PENDING, DUYSTER_MAX_TOTAL_QUEUE,
    _CURSOR, _NEXT, _SEED, _load_candidates, is_non_music_title, canonical_duyster_title,
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

    seed = 77  # Vast zaad maakt de test reproduceerbaar.
    cache = {"__playlist_keys": [], _SEED: seed}
    queue = [{"artist": "Editors", "title": "No Sound But the Wind", "source": "vuurland", "_v116_fifo_seq": 99}]
    original = dict(queue[0])
    base = 1000
    kwargs = dict(data_dir=tmp, key_func=key, allowed=allowed,
                  in_playlist=no_playlist_match)

    all_candidates = _load_candidates(tmp, key)
    all_candidates.sort(key=lambda entry: entry[2])
    random.Random(seed).shuffle(all_candidates)
    expected = [(a, t) for a, t, _ in all_candidates if allowed(a, t)]
    assert len(expected) == 5, expected
    # Aflevering 833 levert 3 geschikte nummers en oudere afleveringen 2.
    assert {a for a, _ in expected} == {
        "Sigur Rós", "Mogwai", "Blanco White", "Cocteau Twins",
        "Ólafur Arnalds",
    }

    actual = []
    for idx in range(len(expected)):
        now = base + idx * 120
        if idx == 1:
            assert enqueue_one(cache, queue, set(), now=now-1, **kwargs) is None
        result = enqueue_one(cache, queue, set(), now=now, **kwargs)
        assert result is not None
        actual.append((result["artist"], result["title"]))
        assert actual == expected[:idx + 1], (actual, expected)
        assert queue[0] == original
        assert cache[_NEXT] == now + 120
        assert cache[_SEED] == seed
    assert enqueue_one(cache, queue, set(), now=base + 600, **kwargs) is None
    assert len(queue) == 6
    assert all(x.get("source") == "duyster" for x in queue[1:])
    assert len({key(x["artist"], x["title"]) for x in queue}) == len(queue)
    assert all(x["artist"] not in ("Tomte", "Avicii") for x in queue)

    # Na een restart blijft de 120s-rem en de volledige shuffle-cursor bewaard.
    restored_cache = dict(cache)
    assert enqueue_one(restored_cache, queue, set(), now=base + 601, **kwargs) is None
    assert restored_cache[_SEED] == seed
    assert restored_cache[_CURSOR] == cache[_CURSOR]

    # Eerder gelikete, geziene en al gequeue-de nummers overslaan.
    cache2 = {"__playlist_keys": [key("Sigur Rós", "Von")], _SEED: seed}
    queue2 = [{"artist": "Mogwai", "title": "Remurdered", "source": "big_sonic_heaven"}]
    seen2 = {key("Blanco White", "Mano a Mano")}
    remaining = [(a, t) for a, t in expected if
                 key(a, t) not in seen2 and
                 key(a, t) not in cache2["__playlist_keys"] and
                 not (a == "Mogwai" and t == "Remurdered")]
    other = enqueue_one(cache2, queue2, seen2, now=base, **kwargs)
    assert other and (other["artist"], other["title"]) == remaining[0], other

    # Nieuwe uitzending: fingerprint wijzigt, cursor start opnieuw, maar reeds
    # queue-de artiesten worden niet opnieuw aangeboden.
    write_csv(tmp, "duyster_aflevering_833.csv", [
        ("Sigur Rós", "Von", "833", "2026-10-26"),
        ("Mogwai", "Remurdered", "833", "2026-10-26"),
        ("Blanco White", "Mano a Mano", "833", "2026-10-26"),
        ("Tomte", "Ich liebe dich", "833", "2026-10-26"),
        ("Avicii", "Levels", "833", "2026-10-26"),
        ("Midwife", "God Is a Cop", "834", "2026-11-02"),
    ], ("artist", "title", "pid", "episode_date"))
    new = enqueue_one(cache, queue, set(), now=base + 720, **kwargs)
    assert new and new["artist"] == "Midwife", new

    # Een oude v192 volgcursor wordt bij de overstap eenmalig gewist.
    old_cache = {"__playlist_keys": [], _CURSOR: 3}
    item = enqueue_one(old_cache, [], set(), now=base, **kwargs)
    assert item and old_cache[_SEED] >= 0 and old_cache[_CURSOR] > 0

    # FIFO remmen als er al veel Duyster-nummers wachten.
    full_duyster = [{"artist": "X", "title": str(i), "source": "duyster"}
                    for i in range(DUYSTER_MAX_PENDING)]
    assert enqueue_one({}, full_duyster, set(), now=base, **kwargs) is None
    assert len(full_duyster) == DUYSTER_MAX_PENDING
    huge_queue = [{"artist": "X", "title": str(i), "source": "vuurland"}
                  for i in range(DUYSTER_MAX_TOTAL_QUEUE)]
    assert enqueue_one({}, huge_queue, set(), now=base, **kwargs) is None
    assert len(huge_queue) == DUYSTER_MAX_TOTAL_QUEUE

# Historische Radio 1-sessie wordt uitsluitend als studioversie beschouwd.
# Ook dubbels tussen aflevering 833 en de hoofd-CSV krijgen slechts één key.
with tempfile.TemporaryDirectory() as tmp:
    write_csv(tmp, "duyster_aflevering_833.csv", [
        ("Mogwai", "Richie Sacremento (Radio 1 Sessie)", 833, "2026-10-26"),
        ("Recording Artist", "Radio 1 Sessie", 833, "2026-10-26"),
        ("Emma Hessels", "Always Lost (Radio 1 Sessie)", 833, "2026-10-26"),
    ], ("artist", "title", "pid", "episode_date"))
    write_csv(tmp, "duyster_archief_uniek.csv", [
        ("Mogwai", "Richie Sacremento", 810, 1),
        ("Emma Hessels", "Always Lost", 812, 1),
    ], ("artist", "title", "first_seen_pid", "seen_in"))
    studio_candidates = _load_candidates(tmp, key)
    assert [(a, t) for a, t, _ in studio_candidates] == [
        ("Mogwai", "Richie Sacremento"), ("Emma Hessels", "Always Lost")
    ], studio_candidates
    queued = [{"artist": "Mogwai", "title": "Richie Sacremento",
               "source": "big_sonic_heaven", "_v116_fifo_seq": 4}]
    # Mogwai al in de queue: enkel Emma Hessels mag nieuw achteraan komen.
    got = enqueue_one({_SEED: 37}, queued, set(), now=1000,
                      data_dir=tmp, key_func=key,
                      allowed=lambda artist, title: True,
                      in_playlist=no_playlist_match)
    assert got and (got["artist"], got["title"]) == ("Emma Hessels", "Always Lost"), got
    assert len(queued) == 2 and queued[0]["_v116_fifo_seq"] == 4

# De echte publicatie van 833 staat volledig en uniek in het archief.
with (ROOT / "duyster_aflevering_833.csv").open(encoding="utf-8", newline="") as handle:
    recent = list(csv.DictReader(handle))
assert len(recent) == 25
assert all(row["pid"] == "833" and row["episode_date"] == "2026-10-26" for row in recent)
with (ROOT / "duyster_archief_uniek.csv").open(encoding="utf-8", newline="") as handle:
    archive = list(csv.DictReader(handle))
assert len(archive) == 8308, len(archive)
all_keys = {key(row["artist"], row["title"]) for row in archive}
assert all(not is_non_music_title(row["title"]) for row in archive)
for title in ("Interview", "Sessie", "Interview + Sessie",
              "interview & sessie", " INTERVIEW ", "Interview  +   Sessie",
              "Radio 1 Sessie", " (Radio 1 Sessie) "):
    assert is_non_music_title(title), title
    assert canonical_duyster_title(title) is None
for title in ("Interview with the Vampire", "A Sessie (Live)", "This Is An Interview"):
    assert not is_non_music_title(title), title
assert canonical_duyster_title("Richie Sacremento (Radio 1 Sessie)") == "Richie Sacremento"
assert canonical_duyster_title("Always Lost [radio 1 sessie]") == "Always Lost"
assert canonical_duyster_title("Sunbeamer (Acoustic Studio Session)") == "Sunbeamer (Acoustic Studio Session)"
assert any(row["artist"] == "Emma Hessels" and row["title"] == "Always Lost"
           for row in archive)
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

print("✅ Duyster-archief: blijvende shuffle tussen afleveringen, 120s-tempo en FIFO.")
print("✅ Aflevering 833 blijft aanwezig: 25 nummers, 8308 muzieknummers na opschoning.")
print("✅ Geen duplicaten, Duitse zang, EDM, queueverlies of extra Spotify-API-calls.")
