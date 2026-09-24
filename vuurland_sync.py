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
PLAYLIST_ID = "5WkgQBl9M7nHinVD1qd9Ol"

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
    pending_title = None

    import re

    program_labels = {
        "studio brussel vuurland",
        "oud - vrt studio brussel vuurland",
    }

    for element in soup.find_all(["tr", "li"]):

        text = " ".join(element.stripped_strings)

        time_match = re.search(
            r"\b\d{1,2}:\d{2}\b\s*(.*)$",
            text
        )

        if not time_match:
            continue

        entry = time_match.group(1).strip()

        if not entry:
            continue

        entry_lower = entry.lower().strip()

        # Programmavermeldingen zijn geen nummers.
        if entry_lower in program_labels:
            continue

        # Normaal formaat:
        # ARTIST - TITLE
        match = re.match(
            r"^(.+?)\s+-\s+(.+)$",
            entry
        )

        if match:
            artist = match.group(1).strip()
            title = match.group(2).strip()
            pending_title = None

        else:
            # OnlineRadioBox kan soms titel en artiest
            # als afzonderlijke regels tonen.
            #
            # We bewaren een losse titel en wachten op
            # de volgende losse regel die de artiest bevat.
            if pending_title is None:
                pending_title = entry
                continue

            artist = entry
            title = pending_title
            pending_title = None

        program_text = f"{artist} {title}".strip().lower()

        if program_text in program_labels:
            continue

        if len(artist) > 150 or len(title) > 300:
            continue

        key = (
            artist.lower(),
            title.lower()
        )

        if key in seen:
            continue

        seen.add(key)

        tracks.append(
            (artist, title)
        )

    return tracks


# =========================
# NUMMER ZOEKEN
# =========================

def find_spotify_track(
    artist,
    title
):

    if time.time() < SPOTIFY_SEARCH_BLOCKED_UNTIL:
        remaining = int(
            SPOTIFY_SEARCH_BLOCKED_UNTIL - time.time()
        )
        raise RuntimeError(
            f"Spotify Search nog geblokkeerd "
            f"({remaining} seconden resterend)"
        )

    query = (
        f'track:"{title}" '
        f'artist:"{artist}"'
    )

    data = spotify_request(
        "GET",
        "/search",
        params={
            "q": query,
            "type": "track",
            "limit": 5
        }
    )

    items = data.get(
        "tracks",
        {}
    ).get(
        "items",
        []
    )

    wanted_title = title.strip().lower()
    wanted_artist = artist.strip().lower()

    def normalize(value):
        value = value.lower().strip()

        for char in [".", ",", "(", ")", "[", "]"]:
            value = value.replace(char, " ")

        return " ".join(value.split())

    normalized_wanted_title = normalize(wanted_title)
    normalized_wanted_artist = normalize(wanted_artist)

    # Splits samenwerkingen zoals:
    # "BIG RED MACHINE feat TAYLOR SWIFT"
    # "ARTIST & OTHER ARTIST"
    artist_parts = re.split(
        r"\s+(?:feat\.?|ft\.?|featuring)\s+|\s+&\s+",
        normalized_wanted_artist
    )

    artist_parts = [
        part.strip()
        for part in artist_parts
        if part.strip()
    ]

    for item in items:

        spotify_title = normalize(
            item.get("name", "")
        )

        if spotify_title != normalized_wanted_title:
            continue

        spotify_artists = [
            normalize(a.get("name", ""))
            for a in item.get("artists", [])
            if a.get("name")
        ]

        # Eerst exacte artiestennaam proberen.
        if normalized_wanted_artist in spotify_artists:
            return item["uri"]

        # Daarna samenwerkingen controleren.
        # Iedere opgegeven artiest moet in de Spotify-artiesten
        # terug te vinden zijn.
        if (
            len(artist_parts) > 1
            and all(
                any(
                    part == spotify_artist
                    or part in spotify_artist
                    or spotify_artist in part
                    for spotify_artist in spotify_artists
                )
                for part in artist_parts
            )
        ):
            return item["uri"]

    return None


# =========================
# TOEVOEGEN
# =========================

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
# SYNC
# =========================

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

    queued_keys = {
        f"{item.get('artist', '').strip().lower()}|||"
        f"{item.get('title', '').strip().lower()}"
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
            f"{artist_clean.lower()}|||"
            f"{title_clean.lower()}"
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
            f"{newest_artist.strip().lower()}|||"
            f"{newest_title.strip().lower()}"
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

    playlist_id = get_playlist()

    # ---------------------------------
    # SPOTIFY SEARCH LIMIET
    # ---------------------------------

    searches_used = 0
    MAX_SEARCHES_PER_RUN = 1

    # ---------------------------------
    # SPOTIFY PLAYLIST CACHE
    # ---------------------------------

    playlist_keys = set(
        cache.get("__playlist_keys", [])
    )

    playlist_cache_time = cache.get(
        "__playlist_cache_time",
        0
    )

    PLAYLIST_CACHE_SECONDS = 21600  # 6 uur

    if (
        not playlist_keys
        or time.time() - playlist_cache_time
        >= PLAYLIST_CACHE_SECONDS
    ):

        print(
            "📋 Spotify-playlist cache vernieuwen..."
        )

        playlist_keys = set()
        playlist_offset = 0

        while True:

            playlist_data = spotify_request(
                "GET",
                f"/playlists/{playlist_id}/items",
                params={
                    "limit": 50,
                    "offset": playlist_offset,
                },
            )

            playlist_batch = playlist_data.get(
                "items",
                []
            )

            for playlist_item in playlist_batch:

                track = playlist_item.get("item")

                if not track:
                    continue

                playlist_title = (
                    track.get("name", "")
                    .strip()
                    .lower()
                )

                for playlist_artist in track.get(
                    "artists",
                    []
                ):

                    artist_name = (
                        playlist_artist.get(
                            "name",
                            ""
                        )
                        .strip()
                        .lower()
                    )

                    if (
                        artist_name
                        and playlist_title
                    ):
                        playlist_keys.add(
                            f"{artist_name}|||"
                            f"{playlist_title}"
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
        f"{artist.strip().lower()}|||"
        f"{title.strip().lower()}"
    )

    # ---------------------------------
    # AL IN PLAYLIST?
    # ---------------------------------

    if cache_key in playlist_keys:

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

            # Spotify is tijdelijk geblokkeerd.
            # Geen oude nummers inhalen na de blokkade:
            # we starten daarna opnieuw vanaf de actuele radio.
            with open(live_queue_file, "w") as f:
                json.dump(
                    [],
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            save_cache(cache)

            print(
                "🗑️ Live queue geleegd vanwege Spotify-rate-limit."
            )
            print(
                "📻 Na de blokkade wordt opnieuw vanaf "
                "de actuele radio gevolgd."
            )

            # GitHub Actions moet deze runner stoppen.
            raise

        searches_used += 1

        if uri is not None:

            cache[cache_key] = uri
            save_cache(cache)

    # ---------------------------------
    # NIET GEVONDEN
    # ---------------------------------

    if uri is None:

        print(
            f"⚠️ Niet gevonden op Spotify: "
            f"{artist} - {title}"
        )

        # Niet verwijderen.
        # Bij een volgende ronde opnieuw proberen.
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
            f"🔎 Spotify Search gebruikt: "
            f"{searches_used}/{MAX_SEARCHES_PER_RUN}"
        )

        return

    # ---------------------------------
    # TOEVOEGEN AAN SPOTIFY
    # ---------------------------------

    add_tracks(
        playlist_id,
        [uri]
    )

    print(
        f"✅ Toegevoegd: "
        f"{artist} - {title}"
    )

    # Meteen lokaal als bestaand markeren.
    playlist_keys.add(cache_key)

    cache[
        "__playlist_keys"
    ] = sorted(playlist_keys)

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
