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
}

SOURCE_URL = "https://onlineradiobox.com/be/vuurland/playlist/?lang=nl"

CHECK_EVERY_SECONDS = 120  # 2 minuten
SPOTIFY_SEARCH_BLOCKED_UNTIL = 0

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

def get_vuurland_tracks():

    print(
        "📻 Vuurland wordt gecontroleerd..."
    )

    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        },
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    tracks = []
    seen = set()

    import re

    program_labels = {
        "studio brussel vuurland",
        "oud - vrt studio brussel vuurland",
    }

    rows = []

    # ---------------------------------------------------------
    # RADIOBOX-REGELS INLEZEN
    # ---------------------------------------------------------

    for element in soup.find_all(["tr", "li"]):

        text = " ".join(
            element.stripped_strings
        )

        time_match = re.search(
            r"\b(\d{1,2}:\d{2})\b\s*(.*)$",
            text
        )

        if not time_match:
            continue

        time = time_match.group(1)
        entry = time_match.group(2).strip()

        if not entry:
            continue

        entry_lower = entry.lower().strip()

        if entry_lower in program_labels:
            continue

        track_id = None

        link = element.find(
            "a",
            href=re.compile(r"/track/\d+/")
        )

        if link:
            match_id = re.search(
                r"/track/(\d+)/",
                link.get("href", "")
            )

            if match_id:
                track_id = match_id.group(1)

        rows.append(
            {
                "time": time,
                "entry": entry,
                "entry_lower": entry_lower,
                "track_id": track_id,
            }
        )

    # ---------------------------------------------------------
    # HULPFUNCTIE
    # ---------------------------------------------------------

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
            title.lower()
        )

        if key in seen:
            return

        seen.add(key)

        tracks.append(
            (artist, title)
        )

    # ---------------------------------------------------------
    # TRACKS VERWERKEN
    # ---------------------------------------------------------

    i = 0

    while i < len(rows):

        row = rows[i]
        entry = row["entry"]

        # =============================================
        # 1. NORMAAL FORMAAT
        # =============================================

        match = re.match(
            r"^(.+?)\s+-\s+(.+)$",
            entry
        )

        if match:
            add_track(
                match.group(1),
                match.group(2)
            )

            i += 1
            continue

        # =============================================
        # 2. RADIOBOX SPLIT-FORMAAT
        # =============================================
        #
        # RadioBox kan bijvoorbeeld tonen:
        #
        # 16:34  TAYLOR SWIFT feat PHOEBE BRIDGERS
        # 16:34  Nothing new (Taylor's version)
        #
        # Beide regels hebben hetzelfde tijdstip.
        #
        # Alleen wanneer het tijdstip gelijk is, proberen
        # we de twee regels te combineren.
        #
        # We doen dit NIET wanneer beide regels dezelfde
        # tekst hebben.
        # =============================================

        if i + 1 < len(rows):

            next_row = rows[i + 1]

            if (
                row["time"] == next_row["time"]
                and row["entry_lower"] not in program_labels
                and next_row["entry_lower"] not in program_labels
                and row["entry_lower"] != next_row["entry_lower"]
            ):

                # Een volledige ARTIST - TITLE-regel mag
                # nooit als split-record worden gebruikt.
                #
                # De eerste regel wordt als artiest behandeld
                # en de tweede als titel.
                #
                # De bestaande Spotify-matcher blijft daarna
                # verantwoordelijk voor de uiteindelijke
                # veilige match.

                first_is_track = (
                    row["track_id"] is not None
                )

                second_is_track = (
                    next_row["track_id"] is not None
                )

                if first_is_track and second_is_track:

                    add_track(
                        row["entry"],
                        next_row["entry"]
                    )

                    i += 2
                    continue

        # =============================================
        # 3. ONBETROUWBAAR LOS RECORD
        # =============================================

        i += 1

    return tracks


# =========================
# NUMMER ZOEKEN
# =========================

def find_spotify_track(
    artist,
    title
):
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

    search_title = re.sub(
        r"\s*\(?(?:feat\.?|ft\.?|featuring)\s+[^\(\)\[\]]+\)?\s*$",
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
        r"\s+(?:feat\.?|ft\.?|featuring)\s+"
        r"|\s*&\s*"
        r"|\s+and\s+"
        r"|\s*,\s*",
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
    query = (
        f'artist:"{spotify_search_artist}" '
        f'"{search_title}"'
    )

    data = spotify_request(
        "GET",
        "/search",
        params={
            "q": query,
            "type": "track",
            # Spotify Search ondersteunt maximaal 10 resultaten.
            # De kandidaatselectie hieronder blijft streng.
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

    # Kleine Spotify Search-fallback:
    # sommige officiële Spotify-titels worden anders gespeld,
    # bijvoorbeeld:
    #
    # RadioBox: "Speyside"
    # Spotify:  "S P E Y S I D E"
    #
    # Alleen wanneer de eerste zoekopdracht helemaal niets
    # oplevert, proberen we een gespatieerde lettervariant.
    #
    # De bestaande strenge kandidaatmatching blijft daarna
    # volledig verantwoordelijk voor de uiteindelijke match.
    if not items:
        spaced_title = " ".join(
            char
            for char in search_title
            if char.isalnum()
        )

        if spaced_title and spaced_title != search_title:
            fallback_query = (
                f'artist:"{spotify_search_artist}" '
                f'"{spaced_title}"'
            )

            data = spotify_request(
                "GET",
                "/search",
                params={
                    "q": fallback_query,
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

        # Gecontroleerde titelvariant:
        # Beck gebruikt op Spotify "Everybody's Gotta Learn Sometime"
        # terwijl RadioBox "Everybody's got to learn sometime" kan tonen.
        if normalized in {
            "everybody's gotta learn sometime",
            "everybody's got to learn sometime",
        }:
            normalized = "everybody's got to learn sometime"

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

        compacted = "".join(normalized.split())

        parts = normalized.split()

        if len(parts) >= 3 and all(
            len(part) == 1 and part.isalnum()
            for part in parts
        ):
            return "".join(parts)

        return compacted

    def artist_parts(value):
        value = normalize(value)

        parts = re.split(
            r"\s+(?:feat\.?|ft\.?|featuring)\s+"
            r"|\s*&\s*"
            r"|\s+and\s+"
            r"|\s*,\s*",
            value
        )

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]

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
        Verwijder bekende versie-aanduidingen van het einde
        van een Spotify-titel.

        Onbekende varianten blijven onderdeel van de titel.
        """
        value = normalize(value)

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
    wanted_title = normalize(title)
    wanted_title_base = title_base(title)
    wanted_version = requested_version(title)

    wanted_artists = artist_parts(artist)

    # RadioBox vermeldt bij "Never Back Down":
    # "Novastar & Piet Goddaer".
    # Spotify catalogiseert de track onder Novastar.
    # Alleen voor deze expliciet bekende combinatie mag
    # Piet Goddaer als extra RadioBox-credit genegeerd worden.
    if (
        wanted_artists == ["novastar", "piet goddaer"]
        and wanted_title == "never back down"
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
            for spotify_artist in spotify_artist_compact
        )

        primary_artist_exact = any(
            primary_wanted_artist == spotify_artist
            for spotify_artist in spotify_artist_compact
        )

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

        if (
            not primary_artist_exact
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

        # Een expliciete RadioBox-featuring mag niet verdwijnen
        # in een Spotify-kandidaat zonder die featured artiest.
        if (
            wanted_artist_compact[1:]
            and matched_feature_count
            < len(wanted_artist_compact) - 1
        ):
            continue

        # =============================================
        # TITEL CONTROLEREN
        # =============================================

        spotify_title = normalize(
            item.get("name", "")
        )

        if not spotify_title:
            continue

        spotify_title_base = title_base(
            spotify_title
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
            r"(?:\s+\(?(?:feat\.?|ft\.?|featuring)\s+[^\(\)\[\]]+\)?\s*$)",
            "",
            wanted_title,
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

        # Exacte titel.
        if spotify_compact == wanted_compact:
            title_score = 1.0

        # Exacte basistitel na versie-aanduiding.
        elif spotify_base_compact == wanted_base_compact:
            title_score = 0.99

        else:
            title_score = SequenceMatcher(
                None,
                wanted_base_compact,
                spotify_base_compact
            ).ratio()

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
            and title_score < 0.90
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

        elif spotify_base_compact == wanted_base_compact:
            candidate_score += 0.99

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
        if wanted_version:
            if spotify_version == wanted_version:
                candidate_score += 0.50

            elif spotify_version is None:
                candidate_score += 0.10

            else:
                continue

        elif spotify_version is None:
            candidate_score += 0.20

        candidates.append(
            (
                candidate_score,
                -len(candidates),
                item.get("uri")
            )
        )

    if candidates:
        candidates.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1]
            ),
            reverse=True
        )

        return candidates[0][2]

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

    parts = re.split(
        r"\s+(?:feat\.?|ft\.?)\s+|\s*&\s*|\s+and\s+|\s*,\s*",
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

    def compact_artist(value):
        return "".join(
            normalize_match(value).split()
        )

    title_key = normalize_match(title)

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

    # =================================
    # VUURLAND LIVE SYNC
    # =================================

    tracks = get_vuurland_tracks()

    print()
    print(f"   {len(tracks)} nummers gevonden.")

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

    MATCHING_RULES_VERSION = 7

    if cache.get(
        "__matching_rules_version"
    ) != MATCHING_RULES_VERSION:

        cache.pop(
            "sufjan stevens|||love yourself",
            None
        )

        cache[
            "__matching_rules_version"
        ] = MATCHING_RULES_VERSION

        save_cache(cache)

        print(
            "🧹 Oude Sufjan matching-cache verwijderd."
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

    last_radio_key = cache.get("__last_radio_key")

    new_radio_tracks = []

    for artist, title in tracks:

        artist_clean = artist.strip()
        title_clean = title.strip()

        if not artist_clean or not title_clean:
            continue

        # Bron-/programmaregel nooit verwerken.
        if (
            artist_clean.lower() == "oud"
            and title_clean.lower() == "vrt studio brussel vuurland"
        ):
            print(
                f"⏭️ Bronregel overgeslagen: "
                f"{artist_clean} - {title_clean}"
            )
            continue

        key = (
            f"{normalize_match(artist_clean)}|||"
            f"{normalize_match(title_clean)}"
        )

        # Eerste keer:
        # alleen het meest recente nummer nemen.
        if last_radio_key is None:
            new_radio_tracks.append(
                {
                    "artist": artist_clean,
                    "title": title_clean
                }
            )
            break

        # Zodra we het vorige nieuwste nummer bereiken,
        # zijn de nummers erboven nieuw sinds de vorige ronde.
        if key == last_radio_key:
            break

        new_radio_tracks.append(
            {
                "artist": artist_clean,
                "title": title_clean
            }
        )

    # De bovenste track is de meest recente.
    if tracks:
        newest_artist, newest_title = tracks[0]

        newest_key = (
            f"{normalize_match(newest_artist)}|||"
            f"{normalize_match(newest_title)}"
        )

        cache["__last_radio_key"] = newest_key

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

    playlist_cache_time = cache.get(
        "__playlist_cache_time",
        0
    )

    PLAYLIST_CACHE_SECONDS = 86400  # 24 uur

    if (
        not playlist_keys
        or time.time() - playlist_cache_time
        >= PLAYLIST_CACHE_SECONDS
    ):

        print(
            "📋 Spotify-playlist cache vernieuwen..."
        )

        playlist_keys = set()
        playlist_uris = set()
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

        cache[
            "__playlist_keys"
        ] = sorted(playlist_keys)

        cache[
            "__playlist_uris"
        ] = sorted(playlist_uris)

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
        return

    cache_key = (
        f"{normalize_match(artist)}|||"
        f"{normalize_match(title)}"
    )

    # ---------------------------------
    # AL IN PLAYLIST?
    # ---------------------------------

    if (
        cache_key in playlist_keys
        or radio_matches_playlist(
            artist,
            title,
            playlist_keys
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

        return

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

        return

    # ---------------------------------
    # CACHE SEARCH RESULT
    # ---------------------------------

    if cache_key in cache:

        uri = cache[cache_key]

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
            return

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

            cache[cache_key] = uri

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

        return

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

        return

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
