"""v194 offline: 12 rapporten / 146 unieke titels -> 10 veilige herkansingen.

Test alleen identiteits- en FIFO-beslissingen. Geen Spotify-/web-API,
geen echte wachtrij-, cache-, playlist- of like-mutaties.
"""
import ast
from pathlib import Path

from v194_matcher_metadata import (
    canonical_artist, canonical_title, artist_join_key,
    normalize_explicit_version, clearly_truncated_final_word,
)
from v194_report_requeue import REVIEWED, release_report_retries, _DONE

assert len(REVIEWED) == 10 and len(set(REVIEWED)) == 10

# Echte rapportgevallen: alleen expliciete vormvarianten.
assert canonical_title("Birkii", "Holy War - Birkii") == "Holy War"
assert canonical_title("Nada Surf", "Where Is My Mind? - Nada Surf") == "Where Is My Mind?"
assert canonical_title("The 6ths With Lloyd Cole",
                       "Human (featuring Lloyd Cole) - The 6ths With Lloyd Cole") == "Human (featuring Lloyd Cole)"
assert canonical_title("Foo", "This is Foo") == "This is Foo"
assert canonical_title("Aerial Love Feed", "Someone") == "Someone"
assert canonical_title("Birkii", "Holy War - Birkii Remix") == "Holy War - Birkii Remix"
assert canonical_artist("Decemberists, The") == "The Decemberists"
assert canonical_artist("The Antlers") == "The Antlers"
assert canonical_artist("EoB") == "EoB"
assert artist_join_key("Eva & Manu") == artist_join_key("Eva + Manu")
assert artist_join_key("Nick Cave & Neko Case") == artist_join_key("Nick Cave and Neko Case")
assert artist_join_key("Nick Cave & Neko Case") != artist_join_key("Nick Cave & Warren Ellis")
assert artist_join_key("Eva & Manu") != artist_join_key("Eva & Magda")
assert normalize_explicit_version("The Velvet Blues (Ext. Version)") == "The Velvet Blues (Extended Version)"
assert normalize_explicit_version("Wild Creatures") == "Wild Creatures"
assert normalize_explicit_version("The Velvet Blues (Radio Edit)") == "The Velvet Blues (Radio Edit)"
assert clearly_truncated_final_word(
    "The First Time Ever I Saw Your", "The First Time Ever I Saw Your Face")
assert not clearly_truncated_final_word("Someone", "Someone New")
assert not clearly_truncated_final_word("The Village", "The Village Girl")
assert not clearly_truncated_final_word(
    "Where Is My Mind", "Where Is My Mind Gone")
assert not clearly_truncated_final_word(
    "The First Time Ever I Saw Your", "The First Time Ever I Saw Your Face Again")
assert not clearly_truncated_final_word(
    "The First Time Ever I Saw Your", "The First Time Ever I Saw My Face")


def key(a, b):
    return a.strip().casefold() + "|||" + b.strip().casefold()


def in_playlist(a, b, known):
    return key(a, b) in known


active_sources = ("vuurland", "mellow_mix", "big_sonic_heaven",
                  "radio_x_chilled", "dreampop_radio", "indie_select",
                  "dkfm_edge", "dark_edge")

# Twee gevallen staan al ergens vooraan in de radio-FIFO. NIET dupliceren,
# maar uitsluitend de huidige retry-/cooldown-status van exact die items
# vrijgeven. De bestaande _v116_fifo_seq moet behouden blijven.
existing_keys = [key(*pair) for pair in REVIEWED[:2]]
queue = [
    {"artist": REVIEWED[i][0], "title": REVIEWED[i][1],
     "source": "indie_select", "_v116_fifo_seq": i + 8,
     "_v34_search_variant": 2, "_v34_retry_at": 999999999999}
    for i in range(2)
]
original_sequences = [item["_v116_fifo_seq"] for item in queue]
cache = {
    "__playlist_keys": [],
    "__v47_radio_discovered": {
        "indie_select": [key(*pair) for pair in REVIEWED]
    },
    "__v51_radio_unmatched": {
        k: {"artist": REVIEWED[i][0], "title": REVIEWED[i][1],
            "source": "indie_select"}
        for i, k in enumerate(existing_keys)
    },
    "__v51_radio_failed_searches": {k: 5 for k in existing_keys},
    "__unrelated_other_key": "preserve-me",
}
old_copies = [id(item) for item in queue]
add, refreshed, unknown = release_report_retries(
    cache, queue, set(), active_sources=active_sources,
    make_key=key, in_playlist=in_playlist, eligible=lambda a, t: True,
)
assert (add, refreshed, unknown) == (8, 2, 0), (add, refreshed, unknown)
assert len(queue) == 10
assert all(id(x) == old_copies[i] for i, x in enumerate(queue[:2]))
assert [x["_v116_fifo_seq"] for x in queue[:2]] == original_sequences
assert all(x["_v34_search_variant"] == 0 and "_v34_retry_at" not in x
           for x in queue[:2])
assert all(x["source"] == "indie_select" for x in queue)
assert len({key(x["artist"], x["title"]) for x in queue}) == len(queue)
assert cache["__unrelated_other_key"] == "preserve-me"
assert not cache["__v51_radio_unmatched"]
assert not cache["__v51_radio_failed_searches"]
assert len(cache[_DONE]) == 10
assert release_report_retries(cache, queue, set(), active_sources=active_sources,
                              make_key=key, in_playlist=in_playlist,
                              eligible=lambda a, t: True) == (0, 0, 0)

# Zonder bewezen bron NOOIT een bron bedenken uit de generieke rapportnaam.
empty_cache = {"__playlist_keys": []}
empty_queue = []
n, existing, unknown = release_report_retries(
    empty_cache, empty_queue, set(), active_sources=active_sources,
    make_key=key, in_playlist=in_playlist, eligible=lambda a, t: True,
)
assert n == existing == 0 and unknown == 10
assert empty_queue == [] and empty_cache[_DONE] == []

# Een nummer dat al geliket/gescand/uitgesloten is mag niet in de FIFO.
k0 = key(*REVIEWED[0])
skip_cache = {
    "__playlist_keys": [k0],
    "__v47_radio_discovered": {"vuurland": [key(*p) for p in REVIEWED]},
}
new_queue = []
n, existing, unknown = release_report_retries(
    skip_cache, new_queue, set(),
    active_sources=active_sources, make_key=key, in_playlist=in_playlist,
    eligible=lambda a, t: a != REVIEWED[1][0],
)
assert n == 8 and existing == 0 and unknown == 0
assert all(key(x["artist"], x["title"]) != k0 for x in new_queue)
assert all(x["artist"] != REVIEWED[1][0] for x in new_queue)

# Als de exacte archived Duyster-misser als bron is bewaard, mag exact die
# herbeoordeeld worden en niet het hele Duyster-archief.
duyster_k = key(*REVIEWED[0])
archive_cache = {
    "__v50_duyster_unmatched": {duyster_k: {"artist": REVIEWED[0][0],
                                           "title": REVIEWED[0][1]}},
}
duyster_queue = []
got = release_report_retries(
    archive_cache, duyster_queue, set(), active_sources=active_sources,
    make_key=key, in_playlist=in_playlist,
    eligible=lambda a, t: key(a, t) == duyster_k,
)
assert got == (1, 0, 0) and duyster_queue[0]["source"] == "duyster"
assert duyster_k not in archive_cache["__v50_duyster_unmatched"]

# Huidige wachtrijbeperkingen blijven gelden, ook bij herkansingen.
full_queue = [{"artist": "test", "title": str(i), "source": "vuurland"}
              for i in range(3600)]
full_cache = {"__v47_radio_discovered": {"vuurland": [key(*REVIEWED[0])]}}
assert release_report_retries(
    full_cache, full_queue, set(), active_sources=active_sources,
    make_key=key, in_playlist=in_playlist, eligible=lambda a,t: True
)[0] == 0
assert len(full_queue) == 3600

# Statische checks: bestaande matcher blijft streng en 1 Search per sync.
source = (Path(__file__).resolve().parent / "vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
for fragment in (
    'v194_canonical_title(artist, title)',
    'v194_canonical_artist(artist)',
    'v194_artist_join_key(wanted_artists[0])',
    'v194_truncated_final_word(',
    'v194_release_reports(',
    '"santogold": ["Santigold"]',
    '"dog is dead": ["D.I.D"]',
    "\"eob\": [\"Ed O'Brien\"]",
    'SPOTIFY_SEARCH_HTTP_LIMIT = 1',
    'max_additions_per_round = 1',
    'AUTOMATIC_PLAYLIST_INVENTORY_ENABLED = False',
    'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)',
):
    assert fragment in source, fragment

print("✅ v194: volledige artiestcredits, dubbele RadioBox-titels, versieafkortingen.")
print("✅ v194: 10 gerichte herkansingen, originele bronnen, FIFO en Spotify-limieten veilig.")
print("✅ v194: ontbrekende bron/andere versie/irrelevante artiest NOOIT goedgekeurd.")
