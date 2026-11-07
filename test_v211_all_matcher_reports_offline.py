"""v211: all 20 remaining ZIP failures get ONLY an evidence-scoped safe path.

Offline; no Spotify calls, no fabricated IDs, no modifications to playlists.
"""
import ast
from pathlib import Path
from v211_report_search_rescue import (
    album_hint, safer_album_query, confirmed_guest_credit,
    mint_julep_catalog_search_title, mint_julep_same_single,
    unconfirmed_song_search, special_requested_version_is_safe,
)
from v203_matcher_upgrade_requeue import applicable_rules

# Exact pairs copied from the user's original ZIP reports (45 & 46).
remaining = [
    ("Clover", "The Things"),
    ("Dean Garcia", "Broke It Down"),
    ("Hollow Coves", "Heatwave"),
    ("Joan Osborne", "Do I Ever Cross Your Mind"),
    ("Mint Julep", "All That We'll Ever Be"),
    ("The Mynabirds", "One Foot"),
    ("93millionmilesfromthesun", "Slowdive"),
    ("Dead Can Dance", "Eleusis"),
    ("Dean Garcia", "All The Same"),
    ("Grizzly Bear", "Boy From School (Hot Chip Cover)"),
    ("Josh Rouse", "Streetlights"),
    ("Le Boeuf Brothers", "Red Velvet (Yellow Then Blue Remix)"),
    ("Natalie Imbruglia", "Leave Me Alone (Portishead Mix)"),
    ("Stephen Duffy & The Lilac Time", "So Far Away"),
    ("THE CHRISTIAN CLUB feat. LUCY RYAN", "Atlas"),
    ("The Killers", "Mr Brightside (Live Acoustic)"),
    ("The Voxx", "Border"),
    ("Torpus & the Art Directors", "The story's all the same"),
    ("Tricky & Gravediggaz", "Hell Is Round the Corner"),
    ("Young Man", "Unfair"),
]
assert len(remaining) == 20 and len({tuple(x.casefold() for x in p) for p in remaining}) == 20
count_album = count_search = count_alias = 0
for artist, title in remaining:
    a = bool(album_hint(artist, title))
    b = bool(unconfirmed_song_search(artist, title))
    c = (confirmed_guest_credit(artist, title) != artist.strip()
         or bool(mint_julep_catalog_search_title(artist, title)))
    assert sum([a,b,c]) == 1, (artist,title,a,b,c)
    count_album += a;count_search += b;count_alias += c
    rules = applicable_rules(artist, title)
    assert any(name.startswith("v211_") for name in rules), (artist,title,rules)
assert (count_album, count_search, count_alias) == (12, 6, 2)

assert safer_album_query("Dean Garcia", "All The Same") == 'track:"All The Same" album:"Doom n Boom"'
assert safer_album_query("Dean Garcia", "Broke It Down") == 'track:"Broke It Down" album:"Doom n Boom"'
assert safer_album_query("The Mynabirds", "One Foot") == 'track:"One Foot" album:"Lovers Know"'
assert safer_album_query("Le Boeuf Brothers", "Red Velvet (Yellow Then Blue Remix)") == 'track:"Red Velvet (Yellow Then Blue Remix)" album:"Remixed"'
assert safer_album_query("The Killers", "Mr Brightside (Live Acoustic)") is None
assert safer_album_query("Dean Garcia", "All the Same (Live)") is None
assert unconfirmed_song_search("The Voxx", "Border") == 'track:"Border" "The Voxx"'
assert unconfirmed_song_search("The Voxx", "Border (Live)") is None
assert unconfirmed_song_search("Torpus & the Art Directors", "The story's all the same") is not None

assert confirmed_guest_credit("THE CHRISTIAN CLUB feat. LUCY RYAN", "Atlas") == "The Christian Club feat. Bobbi Lu"
assert confirmed_guest_credit("THE CHRISTIAN CLUB feat. LUCY RYAN", "Atlas Remix") == "THE CHRISTIAN CLUB feat. LUCY RYAN"
assert confirmed_guest_credit("ANOTHER BAND feat. LUCY RYAN", "Atlas") == "ANOTHER BAND feat. LUCY RYAN"
assert confirmed_guest_credit("THE CHRISTIAN CLUB feat. OTHER ARTIST", "Atlas") == "THE CHRISTIAN CLUB feat. OTHER ARTIST"

assert mint_julep_catalog_search_title("Mint Julep", "All That We'll Ever Be") == "All We'll Ever Be"
assert mint_julep_catalog_search_title("Mint Julep", "All That We'll Ever Be (Live)") is None
assert mint_julep_same_single("Mint Julep", "All That We'll Ever Be", "Mint Julep",
                             "All We'll Ever Be", "All We'll Ever Be")
assert mint_julep_same_single("Mint Julep", "All That We'll Ever Be", "Mint Julep",
                             "All We'll Ever Be", "Wildfire")
for who, radio_title, candidate_artist, candidate_title, album in [
    ("Mint Julep", "All That We'll Ever Be", "Mint Julep", "All We'll Ever Be (Live)", "Wildfire"),
    ("Mint Julep", "All That We'll Ever Be", "Mint Julep", "All We'll Ever Be", "Live Sessions"),
    ("Mint Julep", "All That We'll Ever Be", "Other Band", "All We'll Ever Be", "Wildfire"),
    ("Mint Julep", "All That", "Mint Julep", "All We'll Ever Be", "Wildfire"),
    ("Other Band", "All That We'll Ever Be", "Mint Julep", "All We'll Ever Be", "Wildfire"),
]:
    assert not mint_julep_same_single(who,radio_title,candidate_artist,candidate_title,album)

def safe(artist, title, spotify_title, album, version):
    return special_requested_version_is_safe(artist,title,spotify_title,album,version)
k="The Killers";t="Mr Brightside (Live Acoustic)"
assert safe(k,t,"Mr Brightside - Live Acoustic","Live Lounge","live")
assert not safe(k,t,"Mr Brightside","Hot Fuss",None)
assert not safe(k,t,"Mr Brightside - Live At Connect / 2004","Live","live")
assert not safe(k,t,"Mr Brightside - Acoustic","Acoustic","acoustic")
n="Natalie Imbruglia";t="Leave Me Alone (Portishead Mix)"
assert safe(n,t,"Leave Me Alone (Portishead Mix)","Remixes","mix")
assert safe(n,t,"Leave Me Alone (Portishead Remix)","Various","remix")
assert not safe(n,t,"Leave Me Alone","Portishead Remixes","remix")
assert not safe(n,t,"Leave Me Alone (Other Remix)","Portishead Remixes","remix")
assert not safe(n,t,"Leave Me Alone (Portishead Mix)","Remixes",None)
b="Le Boeuf Brothers";t="Red Velvet (Yellow Then Blue Remix)"
assert safe(b,t,"Red Velvet (Yellow Then Blue Remix)","Remixed","remix")
assert not safe(b,t,"Red Velvet","Remixed",None)
assert not safe(b,t,"Red Velvet (Yellow Then Blue Remix)","Remixed","mix")
assert not safe(b,t,"Red Velvet (Pascal Remix)","Remixed","remix")
assert safe("Unrelated", "Unrelated", "Whatever", "Whatever", None)

# Original source JSON, strict matcher and 120 s Spotify budget are untouched.
sync = (Path(__file__).parent / "vuurland_sync.py").read_text("utf-8")
ast.parse(sync)
for require in (
    "v211_album_query(artist, title)",
    "v211_unconfirmed_search(artist, title)",
    "v211_guest_credit(artist, title)",
    "v211_mint_search_title(artist, title)",
    "v211_mint_same_single(",
    "v211_version_guard(",
    "_v211_had_confirmed_guest = _v211_guest != artist",
    "if _v208_had_explicit_parenthesized_guest or _v211_had_confirmed_guest:",
    "max_additions_per_round = 1",
    '"market": "from_token"',
):
    assert require in sync, require
assert sync.index("v211_version_guard(") < sync.index("# v94: a radio title")
assert sync.index("v211_mint_same_single(") < sync.index("structural_title_match = (")
assert sync.index("v211_album_query(artist, title)") < sync.index('data = spotify_request(\n            "GET",\n            "/search"')
print("✅ v211: 20/20 report misses routed, 12 album hints, 6 search-only, 2 exact identities; wrong versions never accepted.")
