import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests
from bs4 import BeautifulSoup

# =========================
# INSTELLINGEN
# =========================

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")

REDIRECT_URI = "http://127.0.0.1:8888/callback"

PLAYLIST_NAME = "Studio Brussel Vuurland"
PLAYLIST_ID = "555lFTvdRswe9ukybmOM8T"

# Bekende artiest-naamswijzigingen.
#
# BELANGRIJK:
# Dit is GEEN vrije fuzzy artiestenmatch.
# Een alias wordt alleen gebruikt wanneer we expliciet weten
# dat het om dezelfde artiest gaat.
#
# De normale titelcontrole blijft volledig actief.
ARTIST_ALIASES = {
    "the indien": [
        "rianne",
    ],

    # RadioBox schrijft deze artiest als DELVIS.
    # Spotify gebruikt de officiële schrijfwijze Delv!s.
    # Dit geldt voor alle nummers van deze artiest.
    "delvis": [
        "delv!s",
    ],
    "cat stevens": [
        "Yusuf / Cat Stevens",
    ],

    "bob marley": [
        "Bob Marley & The Wailers",
    ],

    "the rascals": [
        "The Young Rascals",
    ],

    "charlie hunter quartet": [
        "Charlie Hunter",
    ],

    "the pretenders": [
        "Pretenders",
    ],

    "novastar piet goddaer": [
        "Novastar",
    ],

}

SOURCE_URL = "https://onlineradiobox.com/be/vuurland/playlist/?lang=nl"
MELLOW_MIX_SOURCE_URL = "https://onlineradiobox.com/us/paradisemellowmix/playlist/?lang=nl"

CHECK_EVERY_SECONDS = 120  # 2 minuten
SPOTIFY_SEARCH_BLOCKED_UNTIL = 0

# Metadata van de laatst gekozen Spotify Search-kandidaat.
# find_spotify_track() blijft gewoon een URI-string teruggeven,
# zodat bestaande code en regressietests niet veranderen.
LAST_SPOTIFY_MATCH_ISRC = None

DATA_DIR = os.environ.get("VUURLAND_DATA_DIR", os.path.expanduser("~"))
TOKEN_FILE = os.path.join(DATA_DIR, ".vuurland_spotify_token.json")
CACHE_FILE = os.path.join(DATA_DIR, ".vuurland_spotify_cache.json")
SEEN_FILE = os.path.join(DATA_DIR, ".vuurland_seen.json")



def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


_startup_cache = load_cache()

# Een verlopen Spotify-rate-limit niet blijven bewaren.
SPOTIFY_SEARCH_BLOCKED_UNTIL = _startup_cache.get(
    "__spotify_search_blocked_until",
    0
)

if SPOTIFY_SEARCH_BLOCKED_UNTIL <= time.time():
    SPOTIFY_SEARCH_BLOCKED_UNTIL = 0
    if "__spotify_search_blocked_until" in _startup_cache:
        del _startup_cache["__spotify_search_blocked_until"]
        save_cache(_startup_cache)

SCOPES = (
    "playlist-read-private playlist-modify-private "
    "playlist-modify-public"
)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"


# =========================
# CONTROLE
# =========================

if not CLIENT_ID:
    print()
    print("❌ Spotify Client ID ontbreekt.")
    print()
    print("Voer eerst in:")
    print("export SPOTIFY_CLIENT_ID='JOUW_CLIENT_ID'")
    print()
    raise SystemExit


# =========================
# SPOTIFY LOGIN
# =========================

def create_pkce():
    verifier = secrets.token_urlsafe(64)

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(
            verifier.encode()
        ).digest()
    ).decode().rstrip("=")

    return verifier, challenge


def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f)

    try:
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def spotify_login():

    verifier, challenge = create_pkce()

    state = secrets.token_urlsafe(24)

    result = {}

    class CallbackHandler(
        http.server.BaseHTTPRequestHandler
    ):

        def do_GET(self):

            parsed = urllib.parse.urlparse(
                self.path
            )

            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = urllib.parse.parse_qs(
                parsed.query
            )

            result["code"] = params.get(
                "code",
                [None]
            )[0]

            result["state"] = params.get(
                "state",
                [None]
            )[0]

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )

            self.end_headers()

            self.wfile.write(
                b"""
                <html>
                <body>
                <h2>Spotify is gekoppeld!</h2>
                <p>Je kunt dit venster sluiten.</p>
                </body>
                </html>
                """
            )

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(
        ("127.0.0.1", 8888),
        CallbackHandler
    )

    thread = threading.Thread(
        target=server.handle_request
    )

    thread.daemon = True
    thread.start()

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }

    url = (
        AUTH_URL
        + "?"
        + urllib.parse.urlencode(params)
    )

    print()
    print("🌐 Spotify wordt geopend...")
    print()

    webbrowser.open(url)

    thread.join(timeout=180)

    server.server_close()

    if result.get("state") != state:
        raise Exception(
            "Spotify login mislukt: verkeerde state."
        )

    if not result.get("code"):
        raise Exception(
            "Geen Spotify code ontvangen."
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type":
                "authorization_code",

            "code":
                result["code"],

            "redirect_uri":
                REDIRECT_URI,

            "client_id":
                CLIENT_ID,

            "code_verifier":
                verifier,
        },
        timeout=30
    )

    response.raise_for_status()

    token = response.json()

    token["created_at"] = int(time.time())

    save_token(token)

    return token


def get_token():

    token = load_token()

    if token:

        expires = (
            token.get("created_at", 0)
            + token.get("expires_in", 3600)
            - 60
        )

        if time.time() < expires:
            return token

        refresh_token = token.get(
            "refresh_token"
        )

        if refresh_token:

            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type":
                        "refresh_token",

                    "refresh_token":
                        refresh_token,

                    "client_id":
                        CLIENT_ID,
                },
                timeout=30
            )

            if response.status_code == 200:

                new_token = response.json()

                if (
                    "refresh_token"
                    not in new_token
                ):
                    new_token[
                        "refresh_token"
                    ] = refresh_token

                new_token[
                    "created_at"
                ] = int(time.time())

                save_token(new_token)

                return new_token

    env_refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if env_refresh_token:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": env_refresh_token,
                "client_id": CLIENT_ID,
            },
            timeout=30
        )
        if response.status_code != 200:
            try:
                error_data = response.json()
                print("Spotify token fout:", error_data.get("error"))
                print("Spotify uitleg:", error_data.get("error_description"))
            except Exception:
                print("Spotify token fout: HTTP", response.status_code)
            response.raise_for_status()

        new_token = response.json()
        if "refresh_token" not in new_token:
            new_token["refresh_token"] = env_refresh_token
        new_token["created_at"] = int(time.time())
        save_token(new_token)
        return new_token

    return spotify_login()


# =========================
# SPOTIFY API
# =========================

def spotify_request(
    method,
    endpoint,
    **kwargs
):

    max_server_errors = 5
    server_errors = 0

    while True:
        # ---------------------------------
        # BEWAARDE SPOTIFY RATE-LIMIT
        # ---------------------------------
        cache = load_cache()
        blocked_until = cache.get(
            "__spotify_api_blocked_until",
            0
        )

        if blocked_until and time.time() < blocked_until:
            remaining = int(blocked_until - time.time())

            print()
            print(
                "⏸️ Spotify rate-limit is nog actief. "
                f"Nog ongeveer {remaining} seconden."
            )

            raise RuntimeError(
                "Spotify rate-limit is nog actief."
            )

        # Blokkering is afgelopen.
        if blocked_until:
            cache.pop(
                "__spotify_api_blocked_until",
                None
            )
            save_cache(cache)

        token = get_token()

        headers = kwargs.pop(
            "headers",
            {}
        )

        headers["Authorization"] = (
            "Bearer "
            + token["access_token"]
        )

        response = requests.request(
            method,
            API_URL + endpoint,
            headers=headers,
            timeout=30,
            **kwargs
        )

        # ---------------------------------
        # SPOTIFY RATE LIMIT
        #
        # Bij 429 stoppen we NIET.
        # Spotify bepaalt hoe lang we wachten.
        # Daarna proberen we dezelfde request opnieuw.
        # ---------------------------------
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")

            try:
                wait = max(1, int(retry_after))
            except (TypeError, ValueError):
                wait = 60

            print()
            print(
                f"⏸️ Spotify rate-limit (429). "
                f"Spotify adviseert {wait} seconden wachten."
            )

            # Korte rate-limits kunnen we veilig zelf uitzitten.
            # Bij een extreem lange blokkering stoppen we deze run.
            # Zo blijft een GitHub-run niet urenlang nutteloos hangen.
            MAX_RATE_LIMIT_WAIT = 600

            if wait > MAX_RATE_LIMIT_WAIT:
                blocked_until = time.time() + wait

                cache = load_cache()
                cache["__spotify_api_blocked_until"] = blocked_until
                save_cache(cache)

                print(
                    "⏸️ Spotify API tijdelijk geblokkeerd. "
                    f"Blokkering opgeslagen voor {wait} seconden."
                )

                raise RuntimeError(
                    "Spotify rate-limit actief. "
                    "Blokkering is opgeslagen voor de volgende run."
                )

            time.sleep(wait)

            print("▶️ Spotify-request wordt opnieuw geprobeerd.")
            continue

        # ---------------------------------
        # TIJDELIJKE SERVERFOUTEN
        # ---------------------------------
        if response.status_code in (500, 502, 503, 504):
            server_errors += 1

            if server_errors > max_server_errors:
                response.raise_for_status()

            wait = min(
                60,
                2 ** (server_errors - 1)
            )

            print(
                f"⚠️ Spotify HTTP {response.status_code}. "
                f"Opnieuw proberen over {wait} seconden..."
            )

            time.sleep(wait)
            continue

        # ---------------------------------
        # TOKEN VERLOPEN
        # ---------------------------------
        if response.status_code == 401:

            save_token({})

            token = get_token()

            headers["Authorization"] = (
                "Bearer "
                + token["access_token"]
            )

            response = requests.request(
                method,
                API_URL + endpoint,
                headers=headers,
                timeout=30,
                **kwargs
            )

        response.raise_for_status()

        if response.content:
            return response.json()

        return {}


# =========================
# SPOTIFY PLAYLIST
# =========================

def get_playlist():
    # Gebruik altijd de bestaande Vuurland-playlist.
    return PLAYLIST_ID


def existing_tracks(playlist_id):
    tracks = set()
    keys = set()
    offset = 0

    while True:
        data = spotify_request(
            "GET",
            f"/playlists/{playlist_id}/items",
            params={
                "limit": 100,
                "offset": offset
            }
        )

        for item in data.get("items", []):
            track = item.get("item")

            if track:
                uri = track.get("uri")

                if uri:
                    tracks.add(uri)

                title = track.get("name", "").strip().lower()
                artists = track.get("artists", [])

                for artist in artists:
                    artist_name = artist.get("name", "").strip().lower()

                    if title and artist_name:
                        keys.add((artist_name, title))

        if not data.get("next"):
            break

        offset += 100

    return tracks, keys


# =========================
# ONLINE RADIO BOX
# =========================

def get_radiobox_tracks(
    source_url,
    source_name,
    program_labels=None,
):
    print(
        f"📻 {source_name} wordt gecontroleerd..."
    )

    response = requests.get(
        source_url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    tracks = []
    seen = set()

    import re

    if program_labels is None:
        program_labels = set()

    program_labels = {
        str(label).lower().strip()
        for label in program_labels
    }

    rows = []

    for element in soup.find_all(["tr", "li"]):
        row_text = " ".join(
            element.stripped_strings
        )

        time_match = re.search(
            r"\b(\d{1,2}:\d{2})\b\s*(.*)$",
            row_text,
        )

        if not time_match:
            continue

        time_value = time_match.group(1)
        entry = time_match.group(2).strip()

        if not entry:
            continue

        entry_lower = entry.lower().strip()

        if entry_lower in program_labels:
            continue

        # Radio Paradise niet-muziekregels nooit verwerken.
        if (
            "commercial-free" in entry_lower
            and "listener-supported" in entry_lower
        ):
            continue

        track_id = None

        link = element.find(
            "a",
            href=re.compile(r"/track/\d+/"),
        )

        if link:
            match_id = re.search(
                r"/track/(\d+)/",
                link.get("href", ""),
            )

            if match_id:
                track_id = match_id.group(1)

        rows.append(
            {
                "time": time_value,
                "entry": entry,
                "entry_lower": entry_lower,
                "track_id": track_id,
            }
        )

    def add_track(artist, title):
        artist = artist.strip()
        title = title.strip()

        if not artist or not title:
            return

        if artist.lower() == title.lower():
            return

        if len(artist) > 150 or len(title) > 300:
            return

        program_text = (
            f"{artist} {title}"
            .strip()
            .lower()
        )

        if program_text in program_labels:
            return

        key = (
            artist.lower(),
            title.lower(),
        )

        if key in seen:
            return

        seen.add(key)

        tracks.append(
            (artist, title)
        )

    i = 0

    while i < len(rows):
        row = rows[i]
        entry = row["entry"]

        # Normaal formaat:
        # ARTIST - TITLE
        match = re.match(
            r"^(.+?)\s+-\s+(.+)$",
            entry,
        )

        if match:
            add_track(
                match.group(1),
                match.group(2),
            )

            i += 1
            continue

        # RadioBox split-formaat:
        # artiest en titel op twee regels
        # met hetzelfde tijdstip.
        if i + 1 < len(rows):
            next_row = rows[i + 1]

            if (
                row["time"] == next_row["time"]
                and row["entry_lower"]
                not in program_labels
                and next_row["entry_lower"]
                not in program_labels
                and row["entry_lower"]
                != next_row["entry_lower"]
            ):
                first_is_track = (
                    row["track_id"] is not None
                )

                second_is_track = (
                    next_row["track_id"] is not None
                )

                if first_is_track and second_is_track:
                    add_track(
                        row["entry"],
                        next_row["entry"],
                    )

                    i += 2
                    continue

        i += 1

    return tracks


def get_vuurland_tracks():
    return get_radiobox_tracks(
        SOURCE_URL,
        "Studio Brussel Vuurland",
        {
            "studio brussel vuurland",
            "oud - vrt studio brussel vuurland",
        },
    )


def get_mellow_mix_tracks():
    return get_radiobox_tracks(
        MELLOW_MIX_SOURCE_URL,
        "Radio Paradise Mellow Mix",
    )


# =========================
# NUMMER ZOEKEN
# =========================

def find_spotify_track(
    artist,
    title
):
    global LAST_SPOTIFY_MATCH_ISRC
    LAST_SPOTIFY_MATCH_ISRC = None

    """
    Zoek een Spotify-track veilig op artiest + titel.

    Regels:
    - De artiest moet betrouwbaar overeenkomen.
    - De titel moet exact of sterk genoeg overeenkomen.
    - Extra officiële Spotify-toevoegingen zoals Live,
      Remastered en Spotify Singles zijn toegestaan.
    - Een ander nummer van dezelfde artiest wordt nooit
      zomaar gekozen.
    - Het beste geldige resultaat wordt gekozen.
    """

    # =============================================
    # EXACT BEKENDE RADIOBOX -> SPOTIFY MAPPINGS
    # =============================================
    #
    # Alleen bewezen uitzonderingen komen hier terecht.
    # Hierdoor hoeven we de algemene matcher NIET losser
    # te maken en kan nooit een willekeurig nummer van
    # dezelfde artiest gekozen worden.
    #
    # Deze controle gebeurt vóór Spotify Search zodat
    # bekende mappings ook werken tijdens een Search-block.

    known_artist = " ".join(
        artist.strip().casefold()
        .replace("feat.", "feat")
        .split()
    )

    known_title = " ".join(
        title.strip().casefold().split()
    )

    known_uri_overrides = {
        (
            "death cab for cutie",
            "love song",
        ): "spotify:track:49edirvFZwWjxAMZJRg1hN",

        (
            "delvis",
            "money",
        ): "spotify:track:60ARQ6JZcL6QxiCRcaEMq6",

        (
            "mount kimbie feat king krule",
            "empty and silent",
        ): "spotify:track:64mpPHhJIs1Fzlk1n7b9Kn",

        (
            "ry x feat hermanos gutierrez",
            "you",
        ): "spotify:track:3r14cTnRNBAXpYfRorUFa7",

        (
            "gabriel rios feat devendra banhart",
            "la torre",
        ): "spotify:track:4k8dMINfckUXvcjDfNm4vP",

        (
            "zita swoon",
            "thinking about you all the time",
        ): "spotify:track:7zmXOkHrbbTtPb8OLamdnC",

        # RadioBox gebruikt DELVIS, Spotify catalogiseert als Delv!s.
        (
            "delvis",
            "walk alone track",
        ): "spotify:track:1TbzpNoZ6rrUTytsAfraik",

        (
            "leon bridges feat lydia kitto",
            "all day, all night",
        ): "spotify:track:3bzPIGOvMnnePP7GzZrwF2",

        # RadioBox toont de verklarende titel tussen haakjes,
        # Spotify gebruikt alleen "PDLIF".
        (
            "bon iver",
            "pdlif (please don't live in fear)",
        ): "spotify:track:0kT1QOkgYYaW0lnMpXY76h",

        # RadioBox-typfout: "THE BAD SEES" i.p.v. "THE BAD SEEDS".
        (
            "nick cave & the bad sees",
            "skeleton tree",
        ): "spotify:track:3iC4tcs4MfcTBXMV2ptj1M",

        (
            "ben kweller feat mj lenderman",
            "oh dorian",
        ): "spotify:track:6DTw1VZjHrH0o9G8IyckwM",

        # RadioBox: ":) (smiley face)"
        # Spotify:  ":)"
        # Bewezen dezelfde track; gebruik exact deze URI.
        (
            "the japanese house",
            ":) (smiley face)",
        ): "spotify:track:36YY9Yeq3XastTeC1e0VmN",

        # Spotify heeft meerdere catalogus-URI's voor
        # The Flaming Lips - Do You Realize??.
        #
        # De bestaande Vuurland-versie die we willen behouden:
        # spotify:track:2DFRFqWNahKtFD112H2iEZ
        #
        # RadioBox gebruikt de Britse spelling "realise".
        (
            "the flaming lips",
            "do you realise",
        ): "spotify:track:2DFRFqWNahKtFD112H2iEZ",

        # Vuurland bedoelt de gewone albumversie van Exile.
        # Zet die exact vast zodat een andere Spotify-catalogusversie
        # niet opnieuw uit de positieve cache kan worden gebruikt.
        (
            "taylor swift feat bon iver",
            "exile",
        ): "spotify:track:4pvb0WLRcMtbPGmtejJJ6y",

        (
            "francis and the lights feat bon iver & kanye west",
            "friends",
        ): "spotify:track:0ZpBPavoID3eDbaXKSWpAD",

        (
            "lana del rey",
            "young & beautiful",
        ): "spotify:track:2nMeu6UenVvwUktBCpLMK9",

        # RadioBox: "Crosses (Bibio remix)"
        # Spotify:  "Crosses - Bibio Rework"
        (
            "jose gonzalez",
            "crosses (bibio remix)",
        ): "spotify:track:2heQS09dKKuGiJqyKApAWz",

        (
            "taylor swift feat the national",
            "coney island",
        ): "spotify:track:3k7ne7VmH43ZPWxPdvPUgR",

        (
            "angélique kidjo",
            "salala (w/ peter gabriel)",
        ): "spotify:track:1AwNQDoTIfpJ2GxwRvyPUN",
        (
            "david bowie",
            "changes",
        ): "spotify:track:0LrwgdLsFaWh9VXIjBRe8t",

        # RadioBox-spelfout:
        # "Kalipono Slack Key"
        #
        # Spotify:
        # "Kaliponi Slack Key"
        (
            "keola & kapono beamer",
            "kalipono slack key",
        ): "spotify:track:7F6WQ31PmRgZ6JeDxnfXaP",

        # RadioBox:
        # The Pretenders - Back On The Chain Gang
        #
        # Spotify:
        # Pretenders - Back on the Chain Gang - 2007 Remaster
        (
            "the pretenders",
            "back on the chain gang",
        ): "spotify:track:4cMHCRLPNoEbpnl2rz6GS9",
        (
            "pretenders",
            "back on the chain gang",
        ): "spotify:track:4cMHCRLPNoEbpnl2rz6GS9",

        # RadioBox:
        # Charlie Hunter Quartet - More Than This (w/ Norah Jones)
        #
        # De algemene matcher vond eerder een verkeerde Spotify-URI.
        # Deze exacte opname is door ons handmatig bevestigd.
        (
            "charlie hunter quartet",
            "more than this (w/ norah jones)",
        ): "spotify:track:5d8L73s2DVUlIi4KENcxeO",
    }

    known_uri = known_uri_overrides.get(
        (known_artist, known_title)
    )

    if known_uri:
        return known_uri

    if time.time() < SPOTIFY_SEARCH_BLOCKED_UNTIL:
        remaining = int(
            SPOTIFY_SEARCH_BLOCKED_UNTIL - time.time()
        )
        raise RuntimeError(
            f"Spotify Search nog geblokkeerd "
            f"({remaining} seconden resterend)"
        )

    import re
    import unicodedata
    from difflib import SequenceMatcher

    # RadioBox kan uitzonderlijk artiest en titel omdraaien.
    # Een veilige generieke indicatie is: het "artiest"-veld draagt een
    # duidelijke versie-aanduiding, terwijl het "titel"-veld een expliciete
    # featuring-credit bevat (zoals Nothing New / Taylor Swift feat...).
    if (
        re.search(
            r"\b(?:taylor'?s\s+version|from\s+the\s+vault|remaster(?:ed)?|radio\s+edit|live)\b",
            str(artist or ""),
            flags=re.IGNORECASE
        )
        and re.search(
            r"\b(?:feat\.?|ft\.?|featuring)\b",
            str(title or ""),
            flags=re.IGNORECASE
        )
    ):
        artist, title = title, artist

    # =============================================
    # SPOTIFY SEARCH-TERM VOORBEREIDEN
    # =============================================
    #
    # RadioBox kan features in de artiest of titel zetten.
    #
    # Bijvoorbeeld:
    # BADBADNOTGOOD feat Sam Herring
    # Time Moves Slow (Feat Sam Herring)
    #
    # Zoek daarom met:
    # - de echte tracktitel zonder titel-feat
    # - iedere RadioBox-artiest afzonderlijk
    #
    # De resultaten worden daarna nog steeds streng
    # gecontroleerd door de matchinglogica hieronder.

    # RadioBox kan een featured artiest achter de titel zetten:
    #
    #   Sail Away (w/ Carl Broemel)
    #   Suddenly (w/ Beatie Wolfe)
    #   More Than This (w/ Norah Jones)
    #   Sing Me to Sleep (w/ Neko Case)
    #
    # Dat stuk hoort bij de artiestenmetadata, niet bij de titel.
    title_feature_match = re.search(
        r"(?:\s+|\s*\()\s*(?:feat\.?|ft\.?|featuring|w/|with)\s+"
        r"([^\(\)\[\]]+?)\)?\s*$",
        str(title or ""),
        flags=re.IGNORECASE
    )

    title_feature_artist = (
        title_feature_match.group(1).strip()
        if title_feature_match
        else None
    )

    search_title = re.sub(
        r"(?:\s+|\s*\()\s*(?:feat\.?|ft\.?|featuring|w/|with)\s+[^\(\)\[\]]+\)?\s*$",
        "",
        title,
        flags=re.IGNORECASE
    ).strip()

    # RadioBox beschrijft de titel ":)" soms als
    # ":) (smiley face)". Voor Spotify Search moet
    # alleen de echte titel gebruikt worden.
    search_title = re.sub(
        r"\s*\(\s*smiley\s+face\s*\)\s*$",
        "",
        search_title,
        flags=re.IGNORECASE
    ).strip()

    # RadioBox kan live-locaties Nederlandstalig formuleren:
    # "Lippy kids (live op Rock Werchter 2011)"
    #
    # Voor Spotify Search gebruiken we hier de basistitel.
    # De strenge versie- en titelcontrole verderop blijft actief.
    search_title = re.sub(
        r"\s*\(\s*live\s+(?:op|at)\b[^)]*\)\s*$",
        "",
        search_title,
        flags=re.IGNORECASE
    ).strip()

    # RadioBox zet soms credits of verklarende context tussen haakjes
    # achter de titel. Dat is geen onderdeel van de muzikale titel.
    # Voorbeelden:
    #   The Whole Night Sky (Bob Weir=Harmony Vocals/Bonnie Raitt=Slide Guitar)
    #   Falling (Twin Peaks Theme)
    # Alleen duidelijke credit-/contextpatronen verwijderen; gewone
    # betekenisvolle haakjestitels blijven onaangeraakt.
    search_title = re.sub(
        r"\s*\((?=[^)]*(?:=|\b(?:vocals?|guitar|bass|drums?|piano|keys?|harmony|theme|theme song|soundtrack)\b))[^)]*\)\s*$",
        "",
        search_title,
        flags=re.IGNORECASE
    ).strip()

    # Bekende Beck-titelvariant:
    # RadioBox: "Everybody's got to learn sometime"
    # Spotify:  "Everybody's Gotta Learn Sometime"
    #
    # Alleen voor deze exacte bekende titel gebruiken we
    # de Spotify-spelling in de zoekopdracht.
    if (
        artist.strip().lower() == "beck"
        and search_title.strip().lower()
        == "everybody's got to learn sometime"
    ):
        search_title = "Everybody's Gotta Learn Sometime"

    search_artists = re.split(
        r"\s+(?:feat\.?|ft\.?|featuring|w/)\s+",
        artist,
        flags=re.IGNORECASE
    )

    search_artists = [
        part.strip()
        for part in search_artists
        if part.strip()
    ]

    # Alleen de primaire artiest als Spotify Search-filter.
    #
    # Featuring-artiesten en kleine schrijfverschillen mogen
    # de zoekopdracht niet al blokkeren.
    #
    # De echte controle gebeurt hieronder.
    primary_search_artist = (
        search_artists[0]
        if search_artists
        else artist.strip()
    )

    # ---------------------------------------------------------
    # BEKENDE ARTIEST-NAAMSWIJZIGINGEN
    # ---------------------------------------------------------

    def alias_key(value):
        value = str(value or "").lower().strip()
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return " ".join(value.split())

    normalized_primary = alias_key(primary_search_artist)

    search_artist_aliases = ARTIST_ALIASES.get(
        normalized_primary,
        []
    )

    spotify_search_artist = (
        search_artist_aliases[0]
        if search_artist_aliases
        else primary_search_artist
    )

    # Zoek op de actuele Spotify-artiestnaam wanneer een
    # expliciete alias bekend is.
    #
    # De kandidaat wordt daarna nog steeds streng gecontroleerd.

    # Zoek op de primaire artiest, maar maak de titel
    # GEEN harde track-filter.
    #
    # Hierdoor kunnen kleine typefouten zoals:
    # "allright" -> "alright"
    # alsnog relevante Spotify-kandidaten opleveren.
    #
    # De kandidaat wordt daarna verplicht door de
    # strenge matchinglogica hieronder gecontroleerd.
    # Houd de artiest gericht, maar maak de titel geen exacte
    # phrase-query. Zo kan Spotify ook kandidaten teruggeven bij
    # kleine RadioBox-spelfouten zoals:
    #
    #   Kalipono Slack Key
    #   Kaliponi Slack Key
    #
    # De uiteindelijke kandidaat moet hieronder nog steeds door
    # alle strenge artiest-, titel- en versiecontroles.
    # Eén brede Spotify Search per track.  De zoekopdracht zelf mag
    # tolerant zijn; de lokale kandidaatcontrole hieronder blijft streng.
    # Geen harde artist:-filter: die blokkeerde geldige catalogusvarianten
    # zoals J.S. Ondara -> Ondara en album/project-credits.
    # Spotify geeft sinds 2026 maximaal 10 resultaten terug. Daarom
    # moet de ene zoekquery niet te veel op een mogelijk afwijkende
    # artieststring leunen. Bij langere/specifieke titels gebruiken we
    # alleen het laatste artiestwoord als zachte ranking-hint. Zo blijven
    # bv. Raymond Kane/Ray Kane en catalogusnaamsvarianten vindbaar, terwijl
    # de volledige artiestnaam hieronder lokaal streng wordt gecontroleerd.
    search_title_words = re.findall(r"[\w'’]+", search_title, flags=re.UNICODE)

    def spotify_search_title_variant(value):
        """
        Maak de ENIGE Spotify-query tolerant voor vormverschillen.
        De uiteindelijke kandidaatcontrole blijft streng op artiest,
        kerntitel en versie, dus bredere recall maakt de beslislaag
        niet losser.
        """
        text = str(value or "").replace("’", "'")

        contractions = {
            "dont": "don't", "cant": "can't", "wont": "won't",
            "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't",
            "werent": "weren't", "havent": "haven't", "hasnt": "hasn't",
            "hadnt": "hadn't", "couldnt": "couldn't", "wouldnt": "wouldn't",
            "shouldnt": "shouldn't", "didnt": "didn't", "doesnt": "doesn't",
            "im": "i'm", "ive": "i've", "ill": "i'll",
            "youre": "you're", "youve": "you've", "youll": "you'll",
            "theyre": "they're", "theyve": "they've", "theyll": "they'll",
            "mustnt": "mustn't", "mightnt": "mightn't", "neednt": "needn't",
            "couldve": "could've", "wouldve": "would've",
            "shouldve": "should've", "lets": "let's",
        }

        parts = re.split(r"(\s+)", text)
        rebuilt = []
        for part in parts:
            key = re.sub(r"[^a-z]", "", part.casefold())
            replacement = contractions.get(key)
            if replacement and part.strip():
                if part[:1].isupper():
                    replacement = replacement[:1].upper() + replacement[1:]
                rebuilt.append(replacement)
            else:
                rebuilt.append(part)
        text = "".join(rebuilt)

        # Catalogusnummering en datumseparators als zoekvorm.
        text = re.sub(r"\bno\.?\s*(\d+)\b", r" \1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"#\s*(\d+)\b", r" \1 ", text)
        text = re.sub(r"(?<=\d)[./-](?=\d)", " ", text)

        # Duidelijke titel-separatoren mogen de Spotify-ranking niet breken.
        text = re.sub(r"\s+[-–—/]\s+", " ", text)
        text = re.sub(r"\s*/\s*", " ", text)

        # Alleen randquotes verwijderen; apostrofs in woorden behouden.
        text = text.strip(' "`“”')
        return " ".join(text.split())

    search_query_title = spotify_search_title_variant(search_title)

    artist_hint_parts = [
        part for part in re.split(r"\s+", str(spotify_search_artist or "").strip())
        if part
    ]

    # Gebruik alleen betekenisvolle artiesttokens als zachte ranking-hint.
    # De volledige artiest wordt lokaal nog steeds streng gevalideerd.
    generic_artist_words = {
        "the", "and", "with", "feat", "featuring", "ft",
        "band", "music", "orchestra", "ensemble", "project",
    }
    safe_artist_hint_parts = []
    for part in artist_hint_parts:
        hint_token = re.sub(r"[^\w]+", "", part.casefold(), flags=re.UNICODE)
        if len(hint_token) < 2 or hint_token in generic_artist_words:
            continue
        safe_artist_hint_parts.append(part)

    safe_artist_hint = " ".join(safe_artist_hint_parts[:2])
    artist_hint = safe_artist_hint or spotify_search_artist

    # Eén Spotify Search per track blijft de harde limiet.
    query = " ".join(
        part for part in (search_query_title, artist_hint)
        if str(part or "").strip()
    )

    data = spotify_request(
        "GET",
        "/search",
        params={
            "q": query,
            "type": "track",
            "limit": 10
        }
    )

    items = data.get(
        "tracks",
        {}
    ).get(
        "items",
        []
    )

    def normalize(value):
        value = str(value or "").lower().strip()

        value = unicodedata.normalize(
            "NFKD",
            value
        )

        value = "".join(
            char
            for char in value
            if not unicodedata.combining(char)
        )

        value = value.replace("’", "'")
        value = value.replace("–", "-")
        value = value.replace("—", "-")
        value = value.replace("+", " ")

        # Catalogi wisselen vaak tussen "&" en "and".  Behandel die
        # schrijfwijzen als gelijk zonder artiestennamen op te splitsen.
        value = re.sub(r"\s*&\s*", " and ", value)

        # Spotify gebruikt soms gestileerde tekens in titels
        # die door de radiofeed als vraagtekens binnenkomen.
        #
        # Voorbeeld:
        #   RadioBox : 22 (over s??n)
        #   Spotify  : 22 (OVER S∞N)
        #
        # Alleen een dubbele ?? tussen letters wordt behandeld
        # als de gestileerde "oo"-klank. Losse vraagtekens
        # blijven onaangeroerd.
        value = re.sub(
            r"(?<=[a-z])\?\?(?=[a-z])",
            "oo",
            value
        )

        # Het Spotify-symbool ∞ wordt in "S∞N" gebruikt
        # als gestileerde "oo".
        value = value.replace("∞", "oo")

        for char in [
            ".", ",", "(", ")", "[", "]",
            "{", "}", "_"
        ]:
            value = value.replace(char, " ")

        return " ".join(value.split())

    def compact(value):
        return "".join(
            normalize(value).split()
        )

    def title_compact(value):
        """
        Compacte titelvergelijking.

        Naast gewone spaties worden ook gespatieerde lettertitels
        gelijkgetrokken:
        "Speyside" <-> "S P E Y S I D E"

        Nummeraanduidingen in titels worden gecontroleerd gelijkgetrokken:
        "nø2", "no. 2", "no 2" en "#2" -> "no2"

        Alleen voor titels; artiestennamen blijven onaangeraakt.
        """
        normalized = normalize(value)

        # Gestileerde ø gelijkstellen aan gewone "o"
        # voor titelvergelijking, bv. "Waltz nø2".
        normalized = normalized.replace("ø", "o")

        # Veilige, algemene spreektaalvarianten die catalogi vaak
        # verschillend uitschrijven.
        phrase_equivalents = (
            (r"\bgotta\b", "got to"),
            (r"\bwanna\b", "want to"),
            (r"\bgonna\b", "going to"),
            (r"\bkinda\b", "kind of"),
            (r"\boutta\b", "out of"),
        )
        for pattern, replacement in phrase_equivalents:
            normalized = re.sub(pattern, replacement, normalized)

        # Apostrofverschillen zijn voor titelidentiteit niet betekenisdragend.
        # Dont <-> Don't en Cello Song <-> 'Cello Song.
        normalized = normalized.replace("'", "")

        # Catalogus-/deelnummering veilig gelijkzetten, maar alleen achter
        # een duidelijke marker: Part II <-> Part 2, Vol. Two <-> Volume 2.
        number_words = {
            "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9", "ten": "10",
            "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
            "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
        }

        def canonical_catalog_number(match):
            marker = match.group(1).lower()
            raw_number = match.group(2).lower()
            number = number_words.get(raw_number, raw_number)
            if marker in {"pt", "part"}:
                marker = "part"
            elif marker in {"vol", "volume"}:
                marker = "volume"
            else:
                marker = "no"
            return f"{marker} {number}"

        normalized = re.sub(
            r"\b(pt|part|vol|volume|no|number)\.?\s*"
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"i|ii|iii|iv|v|vi|vii|viii|ix|x)\b",
            canonical_catalog_number,
            normalized,
        )

        # Trek gecontroleerde nummernotaties gelijk:
        # "no 2", "no2", "#2" -> "no2"
        normalized = re.sub(
            r"\bno\s*(\d+)\b",
            r"no\1",
            normalized
        )

        normalized = re.sub(
            r"#\s*(\d+)\b",
            r"no\1",
            normalized
        )

        # Spotify kan een structureel deelnummer voor de titel zetten:
        #
        #   Part One - Homecoming
        #   Part 1 - Homecoming
        #
        # RadioBox kan alleen "Homecoming" tonen.
        #
        # Alleen een duidelijk "Part <nummer> -" prefix verwijderen.
        normalized = re.sub(
            r"^part\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s*[-:]\s*",
            "",
            normalized,
            flags=re.IGNORECASE
        ).strip()

        # Gecontroleerde titelvariant:
        # "Waltz nø2"
        # "Waltz No. 2"
        # "Waltz, NO. 2 (XO)"
        # "Waltz #2 (XO)"
        if re.fullmatch(
            r"waltz\s+no2(?:\s+xo)?",
            normalized
        ):
            normalized = "waltz no2"

        compacted = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)

        parts = normalized.split()

        if len(parts) >= 3 and all(
            len(part) == 1 and part.isalnum()
            for part in parts
        ):
            return "".join(parts)

        return compacted

    def artist_parts(value):
        value = normalize(value)

        # &, "and" en komma's kunnen deel uitmaken van
        # één officiële artiestennaam:
        #
        # Nick Cave & The Bad Seeds
        # Angus & Julia Stone
        # Crosby, Stills & Nash
        # Emerson, Lake & Palmer
        #
        # Alleen expliciete feature-markers splitsen.
        parts = re.split(
            r"\s+(?:feat\.?|ft\.?|featuring|w/)\s+",
            value
        )

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]

    def title_identity(value):
        """
        Zeer conservatieve titelidentiteit voor catalogusverschillen.

        Alleen vormverschillen worden gelijkgetrokken, nooit betekenis:
        - 12-17-12 / 12/17/12 / 12.17.12
        - Head ... - Road ... / Head .../Road ...
        - 'Cello Song / Cello Song
        - No. 2 / #2 (via title_compact)
        """
        value = normalize(value)
        value = value.lstrip("'\"` ")

        # Datumachtige cijfergroepen: separator is niet betekenisvol.
        value = re.sub(r"(?<=\d)[./-](?=\d)", "", value)

        # Duidelijke titel-separatoren. Alleen een koppelteken met
        # omliggende spaties wordt behandeld als separator; interne
        # woordkoppelteken blijven intact.
        value = re.sub(r"\s+/\s+|\s+-\s+", " ", value)
        value = re.sub(r"\s*/\s*", " ", value)

        return title_compact(value)

    def title_tokens_without_optional_the(value):
        value = normalize(value).lstrip("'\"` ")
        value = value.replace("'", "")
        value = re.sub(r"(?<=\d)[./-](?=\d)", "", value)
        value = re.sub(r"\s+/\s+|\s+-\s+", " ", value)
        value = re.sub(r"\s*/\s*", " ", value)
        return [token for token in value.split() if token]

    def optional_the_equivalent(left, right):
        left_tokens = title_tokens_without_optional_the(left)
        right_tokens = title_tokens_without_optional_the(right)
        if left_tokens == right_tokens:
            return True

        # Hoogstens één los "the" mag aan één kant ontbreken.
        if abs(len(left_tokens) - len(right_tokens)) != 1:
            return False

        longer, shorter = (left_tokens, right_tokens) if len(left_tokens) > len(right_tokens) else (right_tokens, left_tokens)
        for i, token in enumerate(longer):
            if token == "the" and longer[:i] + longer[i + 1:] == shorter:
                return True
        return False

    def version_family(value):
        """Classificeer alleen een duidelijk afgescheiden versie-suffix."""
        raw = str(value or "").strip().lower()
        raw = raw.replace("–", "-").replace("—", "-")

        suffixes = []
        paren = re.search(r"\(([^()]*)\)\s*$", raw)
        if paren:
            suffixes.append(paren.group(1))
        dash = re.search(r"\s+-\s+(.+?)\s*$", raw)
        if dash:
            suffixes.append(dash.group(1))

        for suffix in suffixes:
            if re.search(r"\bremaster(?:ed)?\b", suffix): return "remaster"
            if re.search(r"\blive\b", suffix): return "live"
            if re.search(r"\bacoustic\b", suffix): return "acoustic"
            if re.search(r"\bremix\b", suffix): return "remix"
            if re.search(r"\bmix\b", suffix): return "mix"
            if re.search(r"\bdemo\b", suffix): return "demo"
            if re.search(r"\binstrumental\b", suffix): return "instrumental"
            if re.search(r"\breprise\b", suffix): return "reprise"
            if re.search(r"\balternate|alternative\b", suffix): return "alternate"
            if re.search(r"\bspotify\s+singles?\b", suffix): return "spotify singles"
            if re.search(r"\bunplugged\b", suffix): return "unplugged"
            if re.search(r"\bstripped\b", suffix): return "stripped"
            if re.search(r"\bsession\b", suffix): return "session"
            if re.search(r"\b(?:alternate\s+)?take\s*\d*\b", suffix): return "take"
            if re.search(r"\bmono\b", suffix): return "mono"
            if re.search(r"\bstereo\b", suffix): return "stereo"
            if re.search(r"\bextended\b", suffix): return "extended"
            if re.search(r"\bpiano\s+version\b", suffix): return "piano version"
            if re.search(r"\borchestral\s+version\b", suffix): return "orchestral version"
            if re.search(r"\b(?:re[- ]?record(?:ed|ing)?|taylor'?s\s+version)\b", suffix): return "re-recorded"
            if re.search(r"\bsped\s*up\b", suffix): return "sped up"
            if re.search(r"\bslowed(?:\s*\+?\s*reverb)?\b", suffix): return "slowed"
            if re.search(r"\bnightcore\b", suffix): return "nightcore"
            if re.search(r"\bkaraoke\b", suffix): return "karaoke"
            if re.search(r"\bradio\s+edit\b", suffix): return "edit"
            if re.search(r"\bedit\b", suffix): return "edit"
            if re.search(r"\bsingle\s+version\b", suffix): return "single version"
            if re.search(r"\balbum\s+version\b", suffix): return "album version"
            if re.search(r"\boriginal\s+version\b", suffix): return "original version"
            if re.search(r"\bversion\b", suffix): return "version"
        return None

    def requested_version(value):
        """
        Bepaal welke bekende versie-aanduiding aan het einde
        van een titel staat.

        Voorbeelden:
        - "(live)" -> "live"
        - "- Live at the BBC" -> "live"
        - "(acoustic)" -> "acoustic"
        - "- Acoustic Version" -> "acoustic"
        - "(remix)" -> "remix"
        - "- Radio Edit" -> "radio edit"

        Bekende varianten zoals "Short Reprise" worden herkend.
        """
        raw_value = str(value or "").strip()

        family = version_family(raw_value)
        if family:
            return family

        version_pattern = re.compile(
            r"""
            (?:\s*[-(]\s*)
            (
                live
                |remaster(?:ed)?
                |remix
                |radio\s+edit
                |edit
                |acoustic
                |demo
                |instrumental
                |reprise
                |short\s+reprise
                |alternate(?:\s+version)?
                |version
                |spotify\s+singles
                |unplugged
                |stripped
                |session
                |(?:alternate\s+)?take\s*\d*
                |mono
                |stereo
                |extended
                |piano\s+version
                |orchestral\s+version
                |re[- ]?record(?:ed|ing)?
                |taylor'?s\s+version
                |sped\s*up
                |slowed(?:\s*\+?\s*reverb)?
                |nightcore
                |karaoke
                |single\s+version
                |album\s+version
                |original\s+version
                |deluxe\s+version
                |bonus\s+track
            )
            (?:\s+[^)]*)?
            \s*\)?\s*$
            """,
            re.IGNORECASE | re.VERBOSE
        )

        match = version_pattern.search(raw_value)

        if not match:
            return None

        return match.group(1).lower().strip()


    def title_base(value):
        """
        Verwijder bekende versie-/credit-aanduidingen van een titel.

        RadioBox en Spotify plaatsen featuring-credits, catalogusversies
        en "From The Vault" niet altijd in hetzelfde veld.
        """
        raw_value = str(value or "").strip()

        # Duidelijke RadioBox credit-/contexthaakjes horen niet bij de titel.
        raw_value = re.sub(
            r"\s*\((?=[^)]*(?:=|\b(?:vocals?|guitar|bass|drums?|piano|keys?|harmony|theme|theme song|soundtrack)\b))[^)]*\)\s*$",
            "",
            raw_value,
            flags=re.IGNORECASE
        ).strip()

        # Featuring-credit in de officiële Spotify-titel hoort niet bij
        # de muzikale kerntitel; de artiestenmetadata wordt apart getest.
        raw_value = re.sub(
            r"\s*\((?:feat\.?|ft\.?|featuring)\s+[^)]*\)",
            "",
            raw_value,
            flags=re.IGNORECASE
        )

        # Cataloguslabels die dezelfde opname/titel beschrijven.
        raw_value = re.sub(
            r"\s*\((?:[^)]*?\s+version|from\s+the\s+vault)\)",
            "",
            raw_value,
            flags=re.IGNORECASE
        )

        value = normalize(raw_value)

        # Officiële film-/soundtracktoevoeging.
        motion_picture_pattern = re.compile(
            r"(?:\s+|\[\s*|\(\s*)from\s+the\s+motion\s+picture\b.*(?:\]|\))?\s*$",
            re.IGNORECASE
        )

        value = motion_picture_pattern.sub(
            "",
            value
        ).strip()

        # Gebruik dezelfde bekende versies als requested_version().
        #
        # Omdat normalize() haakjes verwijdert, werken we hier
        # bewust op het genormaliseerde einde van de titel.
        known_suffix_pattern = re.compile(
            r"""
            \s*[-]?\s*
            (
                live
                |remaster(?:ed)?
                |remix
                |radio\s+edit
                |edit
                |acoustic
                |demo
                |instrumental
                |reprise
                |short\s+reprise
                |alternate(?:\s+version)?
                |version
                |spotify\s+singles
                |unplugged
                |stripped
                |session
                |(?:alternate\s+)?take\s*\d*
                |mono
                |stereo
                |extended
                |piano\s+version
                |orchestral\s+version
                |re[- ]?record(?:ed|ing)?
                |taylor'?s\s+version
                |sped\s*up
                |slowed(?:\s*\+?\s*reverb)?
                |nightcore
                |karaoke
                |single\s+version
                |album\s+version
                |original\s+version
                |deluxe\s+version
                |bonus\s+track
            )
            (?:\s+.*)?
            \s*$
            """,
            re.IGNORECASE | re.VERBOSE
        )

        previous = None

        while value != previous:
            previous = value

            match = known_suffix_pattern.search(value)

            if match:
                value = value[:match.start()].strip()
            else:
                break

        return value

    def title_extension_bases(value):
        """
        Mogelijke veilige kerntitels van een officiële Spotify-titel.

        RadioBox laat geregeld verklarende Spotify-suffixen weg, bv.:
        "Can't Catch Me Now" -> "... - From The Hunger Games..."
        "Redemption Song" -> "... - Bob Marley: One Love ..."
        "America" -> "America (What's This Idea)"

        We verwijderen hier alleen een duidelijk afgescheiden suffix.
        De artiestcontrole en ambiguïteitsranking blijven actief.
        """
        raw = str(value or "").strip()
        bases = {title_base(raw)}

        # Duidelijk afgescheiden officiële toelichting.
        for pattern in (r"\s+-\s+", r"\s+\(", r"\s+\["):
            parts = re.split(pattern, raw, maxsplit=1)
            if len(parts) == 2 and parts[0].strip():
                bases.add(normalize(parts[0]))
                bases.add(title_base(parts[0]))

        return {base for base in bases if base}

    wanted_title = normalize(title)
    wanted_title_base = title_base(title)
    wanted_version = requested_version(title)

    wanted_artists = artist_parts(artist)

    # Een feature die achter de RadioBox-titel staat,
    # hoort bij de Spotify-artiesten en moet aanwezig zijn.
    if title_feature_artist:
        normalized_title_feature = normalize(
            title_feature_artist
        )

        if (
            normalized_title_feature
            and normalized_title_feature
            not in wanted_artists
        ):
            wanted_artists.append(
                normalized_title_feature
            )

    # RadioBox vermeldt bij "Never Back Down":
    # "Novastar & Piet Goddaer".
    # Spotify catalogiseert de track onder Novastar.
    # Alleen voor deze expliciet bekende combinatie mag
    # Piet Goddaer als extra RadioBox-credit genegeerd worden.
    if (
        wanted_title == "never back down"
        and wanted_artists in (
            ["novastar & piet goddaer"],
            ["novastar", "piet goddaer"],
        )
    ):
        wanted_artists = ["novastar"]

    if not wanted_title or not wanted_artists:
        return None

    # Bewaar de artiesten in dezelfde volgorde als de radio-input.
    # De eerste artiest is de primaire artiest.
    # De overige artiesten zijn eventuele featuring-artiesten.
    wanted_artist_compact = [
        compact(part)
        for part in wanted_artists
        if compact(part)
    ]

    candidates = []

    for item in items:
        spotify_artist_objects = [
            a
            for a in item.get("artists", [])
            if a.get("name")
        ]

        spotify_artists = [
            normalize(a.get("name", ""))
            for a in spotify_artist_objects
        ]

        if not spotify_artists:
            continue

        # -------------------------------------------------
        # ID-VEILIGE ARTIEST-ALIAS
        # -------------------------------------------------
        #
        # Een expliciete naamswijziging mag alleen matchen
        # wanneer Spotify ook exact de bekende artist-ID
        # teruggeeft.
        #
        # THE INDIEN -> Rianne
        # Spotify artist ID: 1M6DAgCuvRE1Ct0Tsq74Lb
        #
        # Dit voorkomt dat een andere artiest met dezelfde
        # naam per ongeluk als alias wordt geaccepteerd.

        allowed_spotify_artist_ids = set()

        if normalized_primary == "the indien":
            allowed_spotify_artist_ids.add(
                "1M6DAgCuvRE1Ct0Tsq74Lb"
            )

        if allowed_spotify_artist_ids:
            candidate_artist_ids = {
                a.get("id")
                for a in spotify_artist_objects
                if a.get("id")
            }

            if not (
                candidate_artist_ids
                & allowed_spotify_artist_ids
            ):
                continue

        spotify_artist_compact = {
            compact(a)
            for a in spotify_artists
        }

        # De volledige RadioBox-credit kan één officiële
        # artiestnaam zijn, maar Spotify kan echte collabs
        # ook als meerdere artist objects teruggeven.
        #
        # Daarom vergelijken we veilig met beide vormen.
        spotify_artist_match_compact = set(
            spotify_artist_compact
        )

        if len(spotify_artists) > 1:
            spotify_artist_match_compact.add(
                compact(" & ".join(spotify_artists))
            )
            spotify_artist_match_compact.add(
                compact(", ".join(spotify_artists))
            )
            spotify_artist_match_compact.add(
                compact(" and ".join(spotify_artists))
            )

        # =============================================
        # ARTIEST MOET STERK KLIPPEN
        # =============================================
        #
        # De EERSTE artiest is de primaire artiest.
        # Kleine typefouten zijn toegestaan, maar alleen
        # bij een hoge overeenkomst.
        #
        # Featured artiesten mogen op Spotify anders zijn
        # opgebouwd of zelfs ontbreken in de hoofdmetadata.
        # De titel + primaire artiest blijven de veiligheidsgrens.

        primary_wanted_artist = compact(
            wanted_artists[0]
        )

        primary_artist_score = max(
            SequenceMatcher(
                None,
                primary_wanted_artist,
                spotify_artist
            ).ratio()
            for spotify_artist
            in spotify_artist_match_compact
        )

        primary_artist_exact = any(
            primary_wanted_artist == spotify_artist
            for spotify_artist
            in spotify_artist_match_compact
        )

        # "The" aan het begin van een artiestennaam is vaak
        # alleen een catalogusverschil:
        #
        #   The Pretenders <-> Pretenders
        #
        # Alleen het volledige eerste woord "the" negeren.
        # De rest van de artiestennaam moet nog steeds streng kloppen.
        def without_leading_the(value):
            normalized_value = normalize(value)

            if normalized_value.startswith("the "):
                normalized_value = normalized_value[4:]

            return compact(normalized_value)

        wanted_without_the = without_leading_the(
            wanted_artists[0]
        )

        spotify_without_the = {
            without_leading_the(spotify_artist)
            for spotify_artist in spotify_artists
            if spotify_artist
        }

        if spotify_without_the:
            the_artist_score = max(
                SequenceMatcher(
                    None,
                    wanted_without_the,
                    spotify_artist
                ).ratio()
                for spotify_artist in spotify_without_the
            )

            primary_artist_score = max(
                primary_artist_score,
                the_artist_score
            )

            if wanted_without_the in spotify_without_the:
                primary_artist_exact = True

        # Een expliciet bekende naamswijziging mag de oude
        # artiestnaam koppelen aan de actuele Spotify-naam.
        alias_artist_match = any(
            alias_key(spotify_artist)
            in {
                alias_key(alias)
                for alias in search_artist_aliases
            }
            for spotify_artist in spotify_artists
        )

        if alias_artist_match:
            primary_artist_score = 1.0
            primary_artist_exact = True

        # Persoonsnaam-variant met dezelfde familienaam en een duidelijke
        # verkorte/uitgeschreven voornaam. Voorbeeld: Raymond Kane <-> Ray Kane.
        # Dit is bewust beperkt tot tweedelige persoonsnamen; de titelcontrole
        # verderop blijft volledig actief.
        wanted_name_parts = normalize(wanted_artists[0]).split()
        person_name_variant = False

        if len(wanted_name_parts) == 2:
            for spotify_artist in spotify_artists:
                spotify_name_parts = normalize(spotify_artist).split()
                if len(spotify_name_parts) != 2:
                    continue

                wanted_first, wanted_last = wanted_name_parts
                spotify_first, spotify_last = spotify_name_parts

                if (
                    wanted_last == spotify_last
                    and min(len(wanted_first), len(spotify_first)) >= 3
                    and (
                        wanted_first.startswith(spotify_first)
                        or spotify_first.startswith(wanted_first)
                    )
                ):
                    person_name_variant = True
                    break

        if person_name_variant:
            primary_artist_score = max(primary_artist_score, 0.96)

        # RadioBox gebruikt soms een vroegere groepsnaam/projectcredit,
        # terwijl Spotify alleen de huidige/verkorte artiest toont.
        # Voorbeelden uit de echte logs:
        #   J.S. Ondara -> Ondara
        #   Liz Cooper & The Stampede -> Liz Cooper
        #   Stevie Ray Vaughan and Double Trouble -> Stevie Ray Vaughan
        # Dit is GEEN vrije fuzzy match: één volledige naam moet duidelijk
        # in de andere vervat zitten en minstens 6 tekens lang zijn.
        primary_artist_contained = any(
            min(len(primary_wanted_artist), len(spotify_artist)) >= 6
            and (
                primary_wanted_artist in spotify_artist
                or spotify_artist in primary_wanted_artist
            )
            for spotify_artist in spotify_artist_match_compact
        )

        if primary_artist_contained:
            primary_artist_score = max(primary_artist_score, 0.94)

        # Soms zet RadioBox de album-/projectnaam in het artiestveld.
        # Alleen een exacte albumnaam mag zo de artiestcontrole redden;
        # de titel moet verderop nog steeds sterk/exact overeenkomen.
        album_name = normalize(
            (item.get("album") or {}).get("name", "")
        )
        album_as_artist_match = bool(
            album_name
            and compact(album_name) == primary_wanted_artist
        )

        if album_as_artist_match:
            primary_artist_score = max(primary_artist_score, 0.97)

        if (
            not primary_artist_exact
            and not person_name_variant
            and not primary_artist_contained
            and not album_as_artist_match
            and primary_artist_score < 0.90
        ):
            continue

        # Featured artiesten moeten aanwezig zijn wanneer
        # RadioBox ze expliciet vermeldt.
        matched_feature_count = 0

        for wanted_feature in wanted_artist_compact[1:]:

            feature_score = max(
                SequenceMatcher(
                    None,
                    wanted_feature,
                    spotify_artist
                ).ratio()
                for spotify_artist in spotify_artist_compact
            )

            if feature_score >= 0.90 or any(
                wanted_feature in spotify_artist
                or spotify_artist in wanted_feature
                for spotify_artist in spotify_artist_compact
            ):
                matched_feature_count += 1

        # Een RadioBox-feature is sterke bevestiging, maar Spotify kan
        # dezelfde opname soms alleen onder de hoofdartiest catalogiseren.
        # Daarom is een ontbrekende feature geen harde afwijzing meer.
        # De kandidaat krijgt hieronder wel minder score dan een versie
        # waarop de genoemde gastartiest daadwerkelijk aanwezig is.
        missing_feature_count = max(
            0,
            (len(wanted_artist_compact) - 1) - matched_feature_count
        )

        # =============================================
        # TITEL CONTROLEREN
        # =============================================

        spotify_title = normalize(
            item.get("name", "")
        )

        if not spotify_title:
            continue

        spotify_title_base = title_base(
            item.get("name", "")
        )

        spotify_version = requested_version(
            item.get("name", "")
        )

        # Specifieke live-opname met locatie + jaar.
        # Als RadioBox dit expliciet vermeldt, moet Spotify
        # dezelfde locatie én hetzelfde jaar bevatten.
        requested_live_location = re.search(
            r"\blive\s+(?:op|at)\s+(.+?)\s+(\d{4})\s*\)?\s*$",
            str(title or ""),
            flags=re.IGNORECASE
        )

        if requested_live_location:
            requested_venue = normalize(
                requested_live_location.group(1)
            )
            requested_year = requested_live_location.group(2)

            spotify_live_text = normalize(
                item.get("name", "")
            )

            venue_words = [
                word
                for word in re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    requested_venue
                ).split()
                if word
            ]

            spotify_live_words = set(
                re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    spotify_live_text
                ).split()
            )

            if (
                requested_year not in spotify_live_text
                or not all(
                    word in spotify_live_words
                    for word in venue_words
                )
            ):
                continue

        # Featuring-vermeldingen in de RadioBox-titel horen
        # bij de artiestinformatie, niet bij de tracktitel.
        #
        # Bijvoorbeeld:
        # "Time Moves Slow (Feat Sam Herring)"
        # moet ook kunnen matchen met Spotify:
        # "Time Moves Slow"
        wanted_title_for_match = re.sub(
            r"(?:\s+|\s*\()\s*(?:feat\.?|ft\.?|featuring|w/|with)\s+[^\(\)\[\]]+\)?\s*$",
            "",
            search_title,
            flags=re.IGNORECASE
        ).strip()

        # RadioBox: ":) (smiley face)" -> echte titel ":)"
        wanted_title_for_match = re.sub(
            r"\s+smiley\s+face\s*$",
            "",
            wanted_title_for_match,
            flags=re.IGNORECASE
        ).strip()

        wanted_title_base_for_match = title_base(
            wanted_title_for_match
        )

        wanted_compact = title_compact(
            wanted_title_for_match
        )

        spotify_compact = title_compact(
            spotify_title
        )

        wanted_base_compact = title_compact(
            wanted_title_base_for_match
        )

        spotify_base_compact = title_compact(
            spotify_title_base
        )

        wanted_identity = title_identity(wanted_title_for_match)
        spotify_identity = title_identity(item.get("name", ""))
        wanted_base_identity = title_identity(wanted_title_base_for_match)
        spotify_base_identity = title_identity(spotify_title_base)

        structural_title_match = (
            wanted_identity == spotify_identity
            or wanted_base_identity == spotify_base_identity
            or optional_the_equivalent(
                wanted_title_base_for_match,
                spotify_title_base
            )
        )

        spotify_extension_compacts = {
            title_compact(base)
            for base in title_extension_bases(item.get("name", ""))
            if base
        }

        extension_title_match = (
            wanted_base_compact in spotify_extension_compacts
        )

        # Exacte titel.
        if spotify_compact == wanted_compact:
            title_score = 1.0

        # Veilige vormvarianten (separator/datum/quote/optioneel "the").
        elif structural_title_match:
            title_score = 0.997

        # Exacte basistitel na bekende versie-aanduiding.
        elif spotify_base_compact == wanted_base_compact:
            title_score = 0.99

        # RadioBox kan een officiële verklarende suffix weglaten.
        elif extension_title_match:
            title_score = 0.985

        else:
            title_score = SequenceMatcher(
                None,
                wanted_base_compact,
                spotify_base_compact
            ).ratio()

            # Gecontroleerde rescue voor duidelijke RadioBox-metadatafouten:
            # minstens drie opeenvolgende beginwoorden moeten gelijk zijn.
            # Alleen bruikbaar samen met een zeer sterke artiestmatch.
            wanted_words = wanted_title_base_for_match.split()
            spotify_words = spotify_title_base.split()
            shared_prefix_words = 0
            for left, right in zip(wanted_words, spotify_words):
                if left != right:
                    break
                shared_prefix_words += 1

            if (
                shared_prefix_words >= 3
                and primary_artist_score >= 0.97
                and min(len(wanted_words), len(spotify_words)) >= 4
            ):
                title_score = max(title_score, 0.905)

        # Harde veiligheidsgrens voor vrije fuzzy matches.
        #
        # Exacte titels en exacte basistitels zijn hierboven al
        # afgehandeld. Een kandidaat met een zwakke titelovereenkomst
        # mag NOOIT worden gekozen alleen omdat de artiest klopt.
        #
        # Dit voorkomt bijvoorbeeld:
        # RadioBox: "Can't Stand Losing You"
        # Spotify:  een ander nummer van dezelfde artiest.
        #
        # 0.90 laat kleine schrijfverschillen toe, maar blokkeert
        # duidelijk andere titels.
        if (
            spotify_compact != wanted_compact
            and spotify_base_compact != wanted_base_compact
            and not structural_title_match
            and not extension_title_match
            and title_score < 0.93
        ):
            continue

        # =============================================
        # GELDIGE SPOTIFY-MATCH OPSLAAN
        # =============================================
        #
        # Niet meteen het eerste geldige resultaat nemen.
        # Spotify kan een minder goede kandidaat vooraan
        # zetten terwijl een later resultaat beter overeenkomt.
        #
        # De kandidaten worden daarom hieronder beoordeeld
        # op titelkwaliteit. Bij gelijke kwaliteit blijft
        # Spotify's oorspronkelijke volgorde leidend.

        candidate_score = (
            title_score
            + (primary_artist_score * 0.50)
            + (matched_feature_count * 0.05)
        )

        if spotify_compact == wanted_compact:
            candidate_score += 1.00

        elif structural_title_match:
            candidate_score += 0.995

        elif spotify_base_compact == wanted_base_compact:
            candidate_score += 0.99

        elif extension_title_match:
            candidate_score += 0.97

        if album_as_artist_match:
            candidate_score += 0.20

        if primary_artist_contained and not primary_artist_exact:
            candidate_score += 0.08

        candidate_score -= missing_feature_count * 0.08

        # =============================================
        # VERSIEVOORKEUR
        # =============================================
        #
        # Als RadioBox expliciet een versie vraagt,
        # krijgt dezelfde Spotify-versie voorrang.
        #
        # Voorbeeld:
        # RadioBox: Do I Wanna Know? (live)
        # Spotify:  Do I Wanna Know? - Live at the BBC
        #
        # requested_version() herkent "live" aan beide
        # kanten. De exacte versie krijgt daardoor extra
        # gewicht.
        #
        # Als RadioBox expliciet een bekende versie vraagt,
        # mag Spotify geen ANDERE bekende versie leveren.
        #
        # Voorbeeld:
        # RadioBox: "Song (live)"
        # Spotify:  "Song - Live at the BBC"  -> toegestaan
        #
        # RadioBox: "Song (live)"
        # Spotify:  "Song - Acoustic"         -> blokkeren
        # Spotify:  "Song - Remix"            -> blokkeren
        #
        # Een Spotify-kandidaat zonder bekende versie blijft
        # toegestaan: sommige Spotify-titels vermelden hun
        # versie niet expliciet.
        # Versie-hiërarchie:
        # 1) RadioBox vraagt expliciet een versie -> Spotify moet dezelfde
        #    versie-familie leveren. Geen live/remix gokken.
        # 2) RadioBox vraagt de gewone track -> gewone/remaster krijgt
        #    absolute voorkeur. Een neutrale edit/single-version is fallback.
        #    Live/mix/remix/acoustic/demo/instrumental/etc. mogen alleen als
        #    NOODfallback wanneer er geen gewone/remaster/veilige edit-kandidaat
        #    in de Spotify-resultaten zit én artiest + kerntitel vrijwel exact zijn.
        hard_alternative_versions = {
            "live", "mix", "remix", "acoustic", "demo",
            "instrumental", "reprise", "alternate", "spotify singles",
            "unplugged", "stripped", "session", "take", "mono", "stereo",
            "extended", "piano version", "orchestral version",
            "re-recorded", "sped up", "slowed", "nightcore", "karaoke",
        }
        soft_fallback_versions = {
            "edit", "single version", "album version",
            "original version", "version",
        }

        if wanted_version:
            if spotify_version != wanted_version:
                continue
            candidate_score += 0.60
            version_tier = 0
        else:
            if spotify_version in hard_alternative_versions:
                # RadioBox vroeg geen speciale versie. Laat een live/mix/etc.
                # dus NOOIT een gewone/remaster/edit verslaan. Maar als Spotify
                # binnen de enige Search-resultaten uitsluitend zo'n alternatieve
                # opname aanbiedt, mag die als zeer strenge noodfallback mee.
                # Dit is bewust veel strenger dan de normale titelmatch:
                # dezelfde hoofdartiest en praktisch dezelfde KERNTITEL zijn
                # vereist. De tier zorgt dat deze kandidaat pas als laatste wint.
                same_core_title = (
                    spotify_compact == wanted_compact
                    or spotify_base_compact == wanted_base_compact
                    or structural_title_match
                    or extension_title_match
                )
                if not same_core_title or primary_artist_score < 0.98:
                    continue
                candidate_score -= 0.55
                version_tier = 2
            elif spotify_version == "remaster":
                candidate_score += 0.24
                version_tier = 0
            elif spotify_version is None:
                candidate_score += 0.30
                version_tier = 0
            elif spotify_version in soft_fallback_versions:
                # Alleen een zeer sterke titel/artiest mag überhaupt als
                # fallback meedoen. De tier zorgt dat iedere gewone/remaster
                # kandidaat altijd wint, ongeacht kleine scoreverschillen.
                if title_score < 0.985 or primary_artist_score < 0.95:
                    continue
                candidate_score -= 0.20
                version_tier = 1
            else:
                continue

        candidate_isrc = str(
            (item.get("external_ids") or {}).get(
                "isrc",
                ""
            )
        ).strip().upper() or None

        candidates.append(
            (
                -version_tier,
                candidate_score,
                -len(candidates),
                item.get("uri"),
                candidate_isrc,
                item.get("name", ""),
                ", ".join(a.get("name", "") for a in spotify_artist_objects),
            )
        )

    if candidates:
        candidates.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1],
                candidate[2],
            ),
            reverse=True
        )

        # Als twee verschillende opnames praktisch gelijk scoren en de
        # beste kandidaat niet minstens een exacte/zeer sterke match is,
        # liever overslaan dan gokken.
        if (
            len(candidates) > 1
            and candidates[0][3] != candidates[1][3]
            and candidates[0][0] == candidates[1][0]
            and abs(candidates[0][1] - candidates[1][1]) < 0.015
            and candidates[0][1] < 2.40
        ):
            return None

        LAST_SPOTIFY_MATCH_ISRC = candidates[0][4]
        return candidates[0][3]

    print(f"🧪 Spotify-query zonder veilige match: {query}")

    if items:
        preview = []
        for item in items[:5]:
            preview_artist = ", ".join(
                a.get("name", "") for a in item.get("artists", []) if a.get("name")
            )
            preview.append(f"{preview_artist} — {item.get('name', '')}")
        if preview:
            print("🧪 Spotify top-kandidaten afgewezen: " + " | ".join(preview))

    return None

def add_tracks(
    playlist_id,
    uris
):

    if not uris:
        return

    for i in range(
        0,
        len(uris),
        100
    ):

        batch = uris[
            i:i + 100
        ]

        spotify_request(
            "POST",
            f"/playlists/"
            f"{playlist_id}/items",
            json={
                "uris": batch
            }
        )


def get_track_isrc_from_uri(uri):
    """
    Haal de ISRC van exact één Spotify-track op.

    Wordt alleen gebruikt als de ISRC niet al uit:
    - Spotify Search
    - playlist-cache
    bekend is.

    Dus GEEN bulk-fetch en GEEN extra playlistscan.
    """

    prefix = "spotify:track:"

    if not uri or not uri.startswith(prefix):
        return None

    track_id = uri[len(prefix):].strip()

    if not track_id:
        return None

    data = spotify_request(
        "GET",
        f"/tracks/{track_id}"
    )

    isrc = str(
        (data.get("external_ids") or {}).get(
            "isrc",
            ""
        )
    ).strip().upper()

    return isrc or None


def remove_tracks(
    playlist_id,
    uris
):
    """
    Verwijder alleen exact opgegeven Spotify-URI's.

    Wordt voor automatische dedup uitsluitend aangeroepen
    wanneer verschillende URI's exact dezelfde ISRC hebben.
    """

    uris = [
        uri
        for uri in dict.fromkeys(uris)
        if uri
    ]

    if not uris:
        return

    for i in range(0, len(uris), 100):
        batch = uris[i:i + 100]

        spotify_request(
            "DELETE",
            f"/playlists/"
            f"{playlist_id}/items",
            json={
                "items": [
                    {"uri": uri}
                    for uri in batch
                ]
            }
        )


# =========================
# SPOTIFY RATE-LIMIT RESET
# =========================

def reset_live_sync_after_rate_limit(
    live_queue_file,
    cache
):
    """
    Spotify is tijdelijk geblokkeerd.

    BELANGRIJK:
    - De live queue wordt NOOIT gewist.
    - Het radio-startpunt wordt NIET gereset.
    - De volgende run gaat verder waar deze run
      gebleven was.

    Een Spotify-rate-limit is dus alleen een
    tijdelijke pauze en veroorzaakt geen verlies
    van nummers uit de live queue.
    """

    save_cache(cache)

    print(
        "⏸️ Spotify-rate-limit: live queue blijft behouden."
    )

    print(
        "🛡️ Geen nummers uit de live queue verwijderd."
    )

    print(
        "📻 Radio-startpunt blijft behouden."
    )

    print(
        "▶️ Na de blokkade wordt de bestaande queue "
        "verder verwerkt."
    )


# =========================
# SYNC
# =========================

def normalize_match(value):
    """
    Centrale, veilige normalisatie voor artiest/titel-identiteit.

    Doet alleen schrijfwijze-normalisatie:
    - lowercase
    - accenten verwijderen
    - leestekens als spaties behandelen
    - meerdere spaties samenvoegen

    GEEN fuzzy matching.
    Verschillende nummers blijven dus verschillende nummers.
    """
    import unicodedata

    value = str(value or "").strip().lower()

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    for char in [
        ".", ",", "(", ")", "[", "]",
        "{", "}", "_", "+", "–", "—"
    ]:
        value = value.replace(char, " ")

    return " ".join(value.split())


def make_playlist_keys(track):
    """
    Maak meerdere lokale sleutels voor één Spotify-track.

    Hierdoor herkennen we bijvoorbeeld:
    KINGFISHR feat. MATT CORBY - The blade

    ook wanneer Spotify de artiesten afzonderlijk teruggeeft.
    """
    import re

    title = track.get("name", "").strip().lower()

    if not title:
        return set()

    artists = []

    for artist in track.get("artists", []):
        name = normalize_match(
            artist.get("name", "")
        )

        if name:
            artists.append(name)

    keys = set()

    # Normale Spotify-vorm: iedere artiest afzonderlijk.
    for artist in artists:
        keys.add(f"{artist}|||{title}")

    # Gecombineerde vorm: alle Spotify-artiesten samen.
    if artists:
        combined = "|||".join(artists)
        keys.add(f"{combined}|||{title}")

    # Extra gecombineerde vorm met " & ".
    if artists:
        combined_amp = " & ".join(artists)
        keys.add(f"{combined_amp}|||{title}")

    return keys


def normalize_radio_artists(artist_text):
    """
    Zet Vuurland-artiesten zoals:

    KINGFISHR feat. MATT CORBY

    om naar losse artiestnamen.
    """
    import re

    text = normalize_match(artist_text)

    # &, "and" en komma's kunnen deel uitmaken van één
    # officiële artiestennaam. Alleen echte feature-markers
    # worden hier opgesplitst.
    parts = re.split(
        r"\s+(?:feat\.?|ft\.?|featuring|w/)\s+",
        text
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def radio_matches_playlist(
    artist_text,
    title,
    playlist_keys
):
    """
    Controleer lokaal of een Vuurland-track
    al in de Spotify-playlist voorkomt.
    """

    import re

    def compact_artist(value):
        normalized = normalize_match(value)

        # Bekende artiestalias:
        # RadioBox: DELVIS
        # Spotify:  Delv!s
        #
        # normalize_match() kan leestekens/spaties anders
        # representeren, daarom vangen we alleen deze expliciet
        # bekende schrijfwijzen op. Dit is GEEN algemene
        # punctuation-insensitive artiestenmatch.
        if normalized in {
            "delvis",
            "delv!s",
            "delv s",
        }:
            return "delvis"

        return "".join(
            normalized.split()
        )

    title_feature_match = re.search(
        r"\s*\(?(?:feat\.?|ft\.?|featuring|w/)\s+"
        r"([^\(\)\[\]]+?)\)?\s*$",
        str(title or ""),
        flags=re.IGNORECASE
    )

    playlist_feature_artist = (
        title_feature_match.group(1).strip()
        if title_feature_match
        else None
    )

    playlist_match_title = re.sub(
        r"\s*\(?(?:feat\.?|ft\.?|featuring|w/)\s+"
        r"[^\(\)\[\]]+?\)?\s*$",
        "",
        str(title or ""),
        flags=re.IGNORECASE
    ).strip()

    title_key = normalize_match(
        playlist_match_title
    )

    # Kleine RadioBox/Spotify-schrijfvariant:
    # "Waltz nø2" = "Waltz No. 2"
    #
    # Alleen voor de playlist-dedupcontrole.
    # De algemene Spotify-matcher blijft onaangeraakt.
    title_key = title_key.replace("nø", "no ")

    radio_artists = normalize_radio_artists(
        artist_text
    )

    radio_artists = [
        normalize_match(artist)
        for artist in radio_artists
        if normalize_match(artist)
    ]

    if playlist_feature_artist:
        normalized_playlist_feature = normalize_match(
            playlist_feature_artist
        )

        if (
            normalized_playlist_feature
            and normalized_playlist_feature
            not in radio_artists
        ):
            radio_artists.append(
                normalized_playlist_feature
            )

    if not radio_artists or not title_key:
        return False

    # Elke afzonderlijke artiest controleren.
    for artist in radio_artists:

        if f"{artist}|||{title_key}" in playlist_keys:
            return True

        # Ook schrijfwijzen met/zonder spaties.
        compact_key = compact_artist(artist)

        for playlist_key in playlist_keys:

            if "|||" not in playlist_key:
                continue

            playlist_artist, playlist_title = (
                playlist_key.split("|||", 1)
            )

            if playlist_title != title_key:
                continue

            if compact_artist(
                playlist_artist
            ) == compact_key:
                return True

    # Gecombineerde artiesten vergelijken.
    combined = "|||".join(radio_artists)

    if f"{combined}|||{title_key}" in playlist_keys:
        return True

    combined_amp = " & ".join(radio_artists)

    if f"{combined_amp}|||{title_key}" in playlist_keys:
        return True

    return False


def sync():
    global LAST_SPOTIFY_MATCH_ISRC

    # =================================
    # VUURLAND LIVE SYNC
    # =================================

    radio_sources = [
        {
            "id": "vuurland",
            "name": "Studio Brussel Vuurland",
            "tracks": get_vuurland_tracks(),
            "cache_key": "__last_radio_key_vuurland",
        },
        {
            "id": "mellow_mix",
            "name": "Radio Paradise Mellow Mix",
            "tracks": get_mellow_mix_tracks(),
            "cache_key": "__last_radio_key_mellow_mix",
        },
    ]

    print()

    for source in radio_sources:
        print(
            f"   {source['name']}: "
            f"{len(source['tracks'])} nummers gevonden."
        )

    # ---------------------------------
    # LIVE QUEUE
    #
    # Dit is geen oude backlog.
    # Alleen nummers die recent op de radio
    # gezien zijn komen hierin.
    # ---------------------------------

    live_queue_file = os.path.join(
        DATA_DIR,
        "vuurland_live_queue.json"
    )

    try:
        with open(live_queue_file, "r") as f:
            live_queue = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        live_queue = []

    if not isinstance(live_queue, list):
        live_queue = []

    # ---------------------------------
    # CACHE / GEZIEN
    # ---------------------------------

    seen = load_seen()
    cache = load_cache()

    # =================================
    # MATCHING CACHE MIGRATIE
    # =================================
    #
    # Een eerdere matcher kon bij:
    # Sufjan Stevens - Love Yourself
    # de verkeerde versie (Short Reprise) cachen.
    #
    # Alleen deze bekende foutieve search-cache wordt
    # eenmalig verwijderd. De grote playlist-cache blijft
    # volledig behouden.

    MATCHING_RULES_VERSION = 20

    if cache.get(
        "__matching_rules_version"
    ) != MATCHING_RULES_VERSION:

        bad_positive_cache_keys = {
            "sufjan stevens|||love yourself",
            "pinback|||loro",
            "ise|||ik reis door de nacht (live)",
            "the flaming lips|||do you realise",
            "taylor swift feat bon iver|||exile",
        }

        removed_bad_cache_keys = []

        for bad_key in bad_positive_cache_keys:
            if bad_key in cache:
                cache.pop(bad_key, None)
                removed_bad_cache_keys.append(bad_key)

        cache[
            "__matching_rules_version"
        ] = MATCHING_RULES_VERSION

        save_cache(cache)

        if removed_bad_cache_keys:
            print(
                "🧹 Oude foutieve matching-cache verwijderd: "
                + ", ".join(sorted(removed_bad_cache_keys))
            )

    queued_keys = {
        f"{normalize_match(item.get('artist', ''))}|||"
        f"{normalize_match(item.get('title', ''))}"
        for item in live_queue
        if isinstance(item, dict)
    }

    # ---------------------------------
    # RADIO-HISTORIEK BIJHOUDEN
    #
    # Bij de eerste run nemen we alleen
    # het meest recente nummer.
    #
    # Daarna nemen we alle nummers die
    # sinds de vorige controle nieuw zijn.
    # ---------------------------------

    new_radio_tracks = []

    for source in radio_sources:
        tracks = source["tracks"]
        cache_key_name = source["cache_key"]

        # Oude Vuurland-cursor behouden.
        if (
            source["id"] == "vuurland"
            and cache_key_name not in cache
            and "__last_radio_key" in cache
        ):
            cache[cache_key_name] = cache[
                "__last_radio_key"
            ]

        last_radio_key = cache.get(
            cache_key_name
        )

        source_new_tracks = []

        for artist, title in tracks:
            artist_clean = artist.strip()
            title_clean = title.strip()

            if (
                not artist_clean
                or not title_clean
            ):
                continue

            key = (
                f"{normalize_match(artist_clean)}|||"
                f"{normalize_match(title_clean)}"
            )

            # Nieuwe bron:
            # alleen het nieuwste nummer als startpunt.
            #
            # Dus Mellow Mix begint vanaf NU en trekt
            # niet ineens de volledige historie binnen.
            if last_radio_key is None:
                source_new_tracks.append(
                    {
                        "artist": artist_clean,
                        "title": title_clean,
                        "source": source["id"],
                    }
                )
                break

            # We zijn terug bij het laatste nummer
            # dat tijdens de vorige run bovenaan stond.
            if key == last_radio_key:
                break

            source_new_tracks.append(
                {
                    "artist": artist_clean,
                    "title": title_clean,
                    "source": source["id"],
                }
            )

        # De eerste parser-track is de nieuwste.
        if tracks:
            newest_artist, newest_title = tracks[0]

            newest_key = (
                f"{normalize_match(newest_artist)}|||"
                f"{normalize_match(newest_title)}"
            )

            cache[
                cache_key_name
            ] = newest_key

        print(
            f"🛰️ {source['name']}: "
            f"{len(source_new_tracks)} "
            "nieuwe track(s) sinds vorige controle."
        )

        new_radio_tracks.extend(
            source_new_tracks
        )

    # ---------------------------------
    # NIEUWE RADIO-NUMMERS AAN LIVE QUEUE
    # ---------------------------------

    added_to_live_queue = 0

    for item in reversed(new_radio_tracks):

        artist = item["artist"]
        title = item["title"]

        key = (
            f"{artist.strip().lower()}|||"
            f"{title.strip().lower()}"
        )

        if key in queued_keys:
            continue

        # Als het al succesvol verwerkt is,
        # hoeft het niet opnieuw in de queue.
        if key in seen:
            continue

        live_queue.append(item)
        queued_keys.add(key)
        added_to_live_queue += 1

    if added_to_live_queue:
        print(
            f"🆕 {added_to_live_queue} nieuwe "
            "radio-nummers in live queue."
        )
    else:
        print("ℹ️ Geen nieuwe radio-nummers.")

    # ---------------------------------
    # ALS ER GEEN NUMMER TE VERWERKEN IS
    # ---------------------------------

    if not live_queue:

        with open(live_queue_file, "w") as f:
            json.dump(
                [],
                f,
                indent=2,
                ensure_ascii=False
            )

        save_cache(cache)

        print("ℹ️ Live queue is leeg.")
        return

    # ---------------------------------
    # PLAYLIST
    # ---------------------------------

    try:
        playlist_id = get_playlist()

    except RuntimeError as error:
        if "Spotify rate-limit actief" in str(error):
            reset_live_sync_after_rate_limit(
                live_queue_file,
                cache
            )
        raise

    # ---------------------------------
    # SPOTIFY SEARCH LIMIET
    # ---------------------------------

    searches_used = 0
    MAX_SEARCHES_PER_RUN = 1
    NOT_FOUND_COOLDOWN_SECONDS = 86400  # 24 uur

    # ---------------------------------
    # SPOTIFY PLAYLIST CACHE
    # ---------------------------------

    playlist_keys = set(
        cache.get("__playlist_keys", [])
    )

    playlist_uris = set(
        cache.get("__playlist_uris", [])
    )

    playlist_isrcs = set(
        cache.get("__playlist_isrcs", [])
    )

    spotify_uri_isrc = dict(
        cache.get("__spotify_uri_isrc", {})
    )

    playlist_isrc_cache_ready = bool(
        cache.get("__playlist_isrc_cache_ready", False)
    )

    playlist_cache_time = cache.get(
        "__playlist_cache_time",
        0
    )

    PLAYLIST_CACHE_SECONDS = 86400  # 24 uur

    if (
        not playlist_keys
        or not playlist_isrc_cache_ready
        or time.time() - playlist_cache_time
        >= PLAYLIST_CACHE_SECONDS
    ):

        print(
            "📋 Spotify-playlist cache vernieuwen..."
        )

        playlist_keys = set()
        playlist_uris = set()
        playlist_isrcs = set()

        # Voor veilige bestaande-duplicatecleanup:
        # per ISRC onthouden welke verschillende URI's voorkomen.
        playlist_isrc_entries = {}
        playlist_position = 0

        playlist_offset = 0

        while True:

            try:
                playlist_data = spotify_request(
                    "GET",
                    f"/playlists/{playlist_id}/items",
                    params={
                        "limit": 50,
                        "offset": playlist_offset,
                    },
                )

            except RuntimeError as error:
                if "Spotify rate-limit actief" in str(error):
                    reset_live_sync_after_rate_limit(
                        live_queue_file,
                        cache
                    )
                raise

            playlist_batch = playlist_data.get(
                "items",
                []
            )

            for playlist_item in playlist_batch:

                track = playlist_item.get("item")

                if not track:
                    continue

                uri = track.get("uri")

                if uri:
                    playlist_uris.add(uri)

                isrc = str(
                    (track.get("external_ids") or {}).get(
                        "isrc",
                        ""
                    )
                ).strip().upper()

                if uri and isrc:
                    playlist_isrcs.add(isrc)
                    spotify_uri_isrc[uri] = isrc

                    playlist_isrc_entries.setdefault(
                        isrc,
                        []
                    ).append(
                        {
                            "uri": uri,
                            "added_at": (
                                playlist_item.get("added_at")
                                or ""
                            ),
                            "position": playlist_position,
                        }
                    )

                playlist_position += 1

                playlist_title = normalize_match(
                    track.get("name", "")
                )

                for playlist_artist in track.get(
                    "artists",
                    []
                ):

                    artist_name = normalize_match(
                        playlist_artist.get(
                            "name",
                            ""
                        )
                    )

                    if (
                        artist_name
                        and playlist_title
                    ):
                        playlist_keys.add(
                            f"{artist_name}|||"
                            f"{playlist_title}"
                        )

                # Bewaar ook de gecombineerde artiesten-vorm.
                playlist_keys.update(
                    make_playlist_keys(track)
                )

            if not playlist_data.get("next"):
                break

            playlist_offset += len(
                playlist_batch
            )

        # ---------------------------------
        # VEILIGE ISRC DEDUP
        # ---------------------------------
        #
        # Alleen wanneer Spotify voor verschillende URI's
        # EXACT dezelfde ISRC teruggeeft.
        #
        # Zelfde URI meerdere keren wordt hier bewust niet
        # automatisch aangepakt, omdat verwijderen op URI
        # alle voorkomens van die URI kan raken.
        #
        # Bij meerdere verschillende URI's met dezelfde ISRC
        # houden we de meest recent toegevoegde entry.

        duplicate_uris_to_remove = []

        for isrc, entries in playlist_isrc_entries.items():

            latest_per_uri = {}

            for entry in entries:
                uri = entry["uri"]

                previous = latest_per_uri.get(uri)

                current_key = (
                    entry.get("added_at", ""),
                    entry.get("position", -1),
                )

                previous_key = (
                    previous.get("added_at", ""),
                    previous.get("position", -1),
                ) if previous else None

                if (
                    previous is None
                    or current_key > previous_key
                ):
                    latest_per_uri[uri] = entry

            # Eén URI voor deze ISRC = niets te doen.
            if len(latest_per_uri) <= 1:
                continue

            ordered = sorted(
                latest_per_uri.values(),
                key=lambda entry: (
                    entry.get("added_at", ""),
                    entry.get("position", -1),
                )
            )

            keep = ordered[-1]
            remove = ordered[:-1]

            print(
                f"🧹 ISRC-duplicaat: {isrc} "
                f"→ behouden {keep['uri']}"
            )

            for entry in remove:
                print(
                    f"   verwijderen: {entry['uri']}"
                )
                duplicate_uris_to_remove.append(
                    entry["uri"]
                )

        if duplicate_uris_to_remove:
            remove_tracks(
                playlist_id,
                duplicate_uris_to_remove
            )

            playlist_uris.difference_update(
                duplicate_uris_to_remove
            )

            print(
                f"✅ {len(set(duplicate_uris_to_remove))} "
                "dubbele Spotify-URI('s) verwijderd "
                "op basis van exacte ISRC."
            )

        cache[
            "__playlist_keys"
        ] = sorted(playlist_keys)

        cache[
            "__playlist_uris"
        ] = sorted(playlist_uris)

        cache[
            "__playlist_isrcs"
        ] = sorted(playlist_isrcs)

        cache[
            "__spotify_uri_isrc"
        ] = spotify_uri_isrc

        cache[
            "__playlist_isrc_cache_ready"
        ] = True

        cache[
            "__playlist_cache_time"
        ] = int(time.time())

        save_cache(cache)

        print(
            f"🛡️ {len(playlist_keys)} bestaande "
            "Spotify-artiest/titel-combinaties "
            "gecontroleerd."
        )

    else:

        print(
            f"💾 Playlist-cache gebruikt: "
            f"{len(playlist_keys)} bestaande nummers."
        )

    # ---------------------------------
    # LIVE QUEUE VERWERKEN
    # ---------------------------------

    # Per sync-run maximaal één queue-item per radiobron.
    #
    # Beide bronnen krijgen zo een kans in dezelfde ronde,
    # terwijl MAX_SEARCHES_PER_RUN = 1 globaal behouden blijft.
    processed_sources = set()

    for _source_slot in range(2):

        if not live_queue:
            break

        selected_index = None
        selected_source = None

        for index, candidate in enumerate(live_queue):
            source_id = str(
                candidate.get("source") or "vuurland"
            ).strip()

            if source_id not in processed_sources:
                selected_index = index
                selected_source = source_id
                break

        if selected_index is None:
            break

        # De bestaande verwerking gebruikt bewust queue-index 0.
        # Zet daarom het gekozen item tijdelijk vooraan.
        if selected_index != 0:
            selected_item = live_queue.pop(selected_index)
            live_queue.insert(0, selected_item)

        processed_sources.add(selected_source)

        # Nooit ISRC-metadata van het vorige queue-item hergebruiken.
        LAST_SPOTIFY_MATCH_ISRC = None

        item = live_queue[0]

        artist = item["artist"]
        title = item["title"]

        # Bronregel extra beveiliging.
        if (
            artist.strip().lower() == "oud"
            and title.strip().lower()
            == "vrt studio brussel vuurland"
        ):

            print(
                f"⏭️ Bronregel verwijderd: "
                f"{artist} - {title}"
            )

            live_queue.pop(0)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)
            continue

        # Door Mylan gecontroleerd: deze tracks zijn niet
        # beschikbaar op Spotify.
        #
        # Geen Search gebruiken en geen vervangende opname raden.
        permanent_skip_tracks = {
            (
                "1 giant leap",
                "the way you dream",
            ),
            (
                "vision thing",
                "barcode",
            ),
            (
                "elliot easton",
                "walk on walden",
            ),
            (
                "tracy chapman",
                "three little birds live",
            ),
            (
                "alison krauss & union station",
                "lie awake",
            ),
        }

        normalized_skip_key = (
            normalize_match(artist),
            normalize_match(title),
        )

        if normalized_skip_key in permanent_skip_tracks:
            print(
                f"⏭️ Bewust overgeslagen "
                f"(niet op Spotify): "
                f"{artist} - {title}"
            )

            live_queue.pop(0)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)
            continue

        # Expliciet overslaan:
        # RadioBox levert deze klassieke titel afgekapt/ambigu aan.
        # Niet zoeken, om geen willekeurige uitvoering toe te voegen.
        if (
            normalize_match(artist) == "edvard grieg"
            and normalize_match(title).startswith(
                "morning mood allegretto pas"
            )
        ):
            print(
                f"⏭️ Bewust overgeslagen: {artist} - {title}"
            )

            live_queue.pop(0)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)
            continue

        cache_key = (
            f"{normalize_match(artist)}|||"
            f"{normalize_match(title)}"
        )

        # Positieve Search-resultaten zijn matcher-versiegebonden.
        # Zo kan een oude foutieve live/mix-URI nooit opnieuw gebruikt
        # worden nadat de matcherregels verbeterd zijn.
        match_cache_key = (
            f"__match_v{MATCHING_RULES_VERSION}__" + cache_key
        )

        # ---------------------------------
        # AL IN PLAYLIST?
        # ---------------------------------

        # Voor bekende RadioBox/catalogus-afwijkingen vertrouwen
        # we niet op alleen artiest+titel uit de playlist-cache.
        # Eerst moet find_spotify_track() de exact gewenste URI
        # bepalen; daarna doet de harde URI-duplicatecheck zijn werk.
        force_exact_uri_check = (
            normalize_match(artist),
            normalize_match(title)
        ) in {
            (
                "death cab for cutie",
                "love song",
            ),
            (
                "delvis",
                "money",
            ),
            (
                "mount kimbie feat king krule",
                "empty and silent",
            ),
            (
                "ry x feat hermanos gutierrez",
                "you",
            ),
            (
                "gabriel rios feat devendra banhart",
                "la torre",
            ),
            (
                "zita swoon",
                "thinking about you all the time",
            ),
            (
                "delvis",
                "walk alone track",
            ),
            (
                "leon bridges feat lydia kitto",
                "all day, all night",
            ),
            (
                "bon iver",
                "pdlif (please don't live in fear)",
            ),
            (
                "nick cave & the bad sees",
                "skeleton tree",
            ),
            (
                "ben kweller feat mj lenderman",
                "oh dorian",
            ),
            (
                "the japanese house",
                ":) (smiley face)",
            ),
            (
                "the flaming lips",
                "do you realise",
            ),
            (
                "taylor swift feat bon iver",
                "exile",
            ),
            (
                "francis and the lights feat bon iver & kanye west",
                "friends",
            ),
            (
                "lana del rey",
                "young & beautiful",
            ),
            (
                "jose gonzalez",
                "crosses (bibio remix)",
            ),
            (
                "taylor swift feat the national",
                "coney island",
            ),
            (
                "angélique kidjo",
                "salala (w/ peter gabriel)",
            ),
            (
                "david bowie",
                "changes",
            ),
            (
                "charlie hunter quartet",
                "more than this (w/ norah jones)",
            ),
            (
                "keola & kapono beamer",
                "kalipono slack key",
            ),
            (
                "the pretenders",
                "back on the chain gang",
            ),
            (
                "pretenders",
                "back on the chain gang",
            ),
        }

        if (
            not force_exact_uri_check
            and (
                cache_key in playlist_keys
                or radio_matches_playlist(
                    artist,
                    title,
                    playlist_keys
                )
            )
        ):

            print(
                f"⏭️ Al in Spotify: "
                f"{artist} - {title}"
            )

            live_queue.pop(0)
            seen.add(cache_key)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_seen(seen)
            save_cache(cache)

            print(
                f"📋 {len(live_queue)} nummers "
                "blijven in live queue."
            )

            continue

        # ---------------------------------
        # EERDER NIET GEVONDEN
        #
        # Voorkomt dat hetzelfde nummer bij
        # iedere controle opnieuw Search gebruikt.
        # ---------------------------------

        # Een "niet gevonden"-resultaat is afhankelijk van de
        # huidige Spotify-matchingregels.
        #
        # Als de matcher later verbeterd wordt, mag een oude
        # mislukte zoekpoging de nieuwe matcher niet blokkeren.
        not_found_key = (
            f"__not_found_v{MATCHING_RULES_VERSION}__"
            + cache_key
        )

        not_found_time = cache.get(
            not_found_key
        )

        if (
            not_found_time is not None
            and time.time() - not_found_time
            < NOT_FOUND_COOLDOWN_SECONDS
        ):

            # Het nummer blijft behouden, maar gaat achteraan
            # de queue zodat andere nummers eerst verwerkt worden.
            failed_item = live_queue.pop(0)
            live_queue.append(failed_item)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)

            print(
                f"🔄 Tijdelijk overgeslagen en achteraan "
                f"de queue geplaatst: {artist} - {title}"
            )

            print(
                f"📋 {len(live_queue)} nummers "
                "blijven in live queue."
            )

            continue

        # ---------------------------------
        # CACHE SEARCH RESULT
        # ---------------------------------

        if match_cache_key in cache:

            uri = cache[match_cache_key]

            print(
                f"💾 Spotify-cache gebruikt: "
                f"{artist} - {title}"
            )

        else:

            if searches_used >= MAX_SEARCHES_PER_RUN:

                print(
                    "⏸️ Spotify Search-limiet "
                    "voor deze ronde bereikt."
                )

                with open(live_queue_file, "w") as f:
                    json.dump(
                        live_queue,
                        f,
                        indent=2,
                        ensure_ascii=False
                    )

                save_cache(cache)
                continue

            print(
                f"🔎 Spotify zoeken: "
                f"{artist} - {title}"
            )

            try:

                uri = find_spotify_track(
                    artist,
                    title
                )

            except RuntimeError as error:

                print(
                    f"⏸️ Spotify pauzeert: {error}"
                )

                reset_live_sync_after_rate_limit(
                    live_queue_file,
                    cache
                )

                # GitHub Actions moet deze runner stoppen.
                raise

            searches_used += 1

            if uri is not None:

                cache[match_cache_key] = uri

                # Een eerdere mislukte zoekpoging is niet meer relevant.
                cache.pop(not_found_key, None)

                save_cache(cache)

        # ---------------------------------
        # NIET GEVONDEN
        # ---------------------------------

        if uri is None:

            print(
                f"⚠️ Geen betrouwbare Spotify-match gevonden: "
                f"{artist} - {title}"
            )

            print(
                "ℹ️ Dit betekent niet dat het nummer niet op Spotify "
                "bestaat; alleen dat de huidige zoekactie geen "
                "veilige match opleverde."
            )

            # 24 uur geen nieuwe Search voor dit nummer.
            cache[not_found_key] = int(time.time())

            # Uit de huidige queue-positie verwijderen.
            #
            # Het nummer wordt NIET vergeten: de __not_found__
            # cooldown-cache zorgt ervoor dat het later opnieuw
            # geprobeerd kan worden.
            live_queue.pop(0)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)

            print(
                f"📋 {len(live_queue)} nummers "
                "blijven in live queue."
            )

            print(
                "🕒 Dit nummer wordt 24 uur niet "
                "opnieuw gezocht."
            )

            print(
                f"🔎 Spotify Search gebruikt: "
                f"{searches_used}/{MAX_SEARCHES_PER_RUN}"
            )

            continue

        # ---------------------------------
        # HARDE ISRC DUPLICATECHECK
        # ---------------------------------
        #
        # Een Spotify-opname kan op meerdere releases onder een
        # andere URI voorkomen. De ISRC identificeert de opname.
        #
        # Geen fuzzy titelvergelijking en geen extra Spotify-GET.

        candidate_isrc = (
            LAST_SPOTIFY_MATCH_ISRC
            or spotify_uri_isrc.get(uri)
        )

        # Search-resultaten hebben hun ISRC al.
        # Bekende/cached URI's soms niet.
        #
        # Alleen in dat laatste geval doen we exact één kleine
        # GET voor deze kandidaat. Geen volledige playlistscan.
        if not candidate_isrc:
            candidate_isrc = get_track_isrc_from_uri(uri)

        if candidate_isrc:
            candidate_isrc = str(
                candidate_isrc
            ).strip().upper()

            spotify_uri_isrc[uri] = candidate_isrc

            cache[
                "__spotify_uri_isrc"
            ] = spotify_uri_isrc

        if (
            candidate_isrc
            and candidate_isrc in playlist_isrcs
        ):
            print(
                f"⏭️ Zelfde Spotify-opname staat al in "
                f"de playlist (ISRC {candidate_isrc}): "
                f"{artist} - {title}"
            )

            live_queue.pop(0)
            seen.add(cache_key)

            save_seen(seen)
            save_cache(cache)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            continue

        # ---------------------------------
        # HARDE URI DUPLICATECHECK
        # ---------------------------------
        #
        # Ook als de oudere playlist-cache dit nummer
        # niet herkende, mag een bestaande Spotify-URI
        # nooit opnieuw worden toegevoegd.
        if uri in playlist_uris:

            print(
                f"⏭️ Spotify-track staat al in de playlist: "
                f"{artist} - {title}"
            )

            live_queue.pop(0)
            seen.add(cache_key)

            save_seen(seen)
            save_cache(cache)

            with open(live_queue_file, "w") as f:
                json.dump(
                    live_queue,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            continue

        # ---------------------------------
        # TOEVOEGEN AAN SPOTIFY
        # ---------------------------------

        add_tracks(
            playlist_id,
            [uri]
        )

        # Meteen lokaal als bestaande Spotify-URI markeren.
        # Zo kan dezelfde URI later in deze run niet opnieuw
        # worden toegevoegd.
        playlist_uris.add(uri)

        if candidate_isrc:
            playlist_isrcs.add(candidate_isrc)
            spotify_uri_isrc[uri] = candidate_isrc

        print(
            f"✅ Toegevoegd: "
            f"{artist} - {title}"
        )

        # Meteen lokaal als bestaand markeren.
        playlist_keys.add(cache_key)

        cache[
            "__playlist_keys"
        ] = sorted(playlist_keys)

        cache[
            "__playlist_uris"
        ] = sorted(playlist_uris)

        cache[
            "__playlist_isrcs"
        ] = sorted(playlist_isrcs)

        cache[
            "__spotify_uri_isrc"
        ] = spotify_uri_isrc

        cache[
            "__playlist_isrc_cache_ready"
        ] = True

        save_cache(cache)

        # Uit live queue verwijderen.
        live_queue.pop(0)

        seen.add(cache_key)
        save_seen(seen)

        with open(live_queue_file, "w") as f:
            json.dump(
                live_queue,
                f,
                indent=2,
                ensure_ascii=False
            )

        save_cache(cache)

        print()
        print(
            f"📋 {len(live_queue)} nummers "
            "in live queue."
        )

        print(
            f"🔎 Spotify Search gebruikt: "
            f"{searches_used}/{MAX_SEARCHES_PER_RUN}"
        )


# =========================
# START
# =========================

if __name__ == "__main__":
    print()
    print("===================================")
    print("   VUURLAND → SPOTIFY")
    print("===================================")
    print()

    try:
        sync()
    except Exception as error:
        print()
        print("❌ Er ging iets mis:")
        print(error)
        raise
