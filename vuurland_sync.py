import base64
import hashlib
import http.server
import json
import os
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

CHECK_EVERY_SECONDS = 60  # 1 minuut
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

    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", "60"))
        if endpoint == "/search":
            globals()["SPOTIFY_SEARCH_BLOCKED_UNTIL"] = time.time() + wait
            cache = load_cache()
            cache["__spotify_search_blocked_until"] = SPOTIFY_SEARCH_BLOCKED_UNTIL
            save_cache(cache)
        raise RuntimeError(f"Spotify rate limit actief (wachtadvies: {wait} seconden)")

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

    for element in soup.find_all(
        ["tr", "li"]
    ):

        text = " ".join(
            element.stripped_strings
        )

        match = re.search(
            r"\b\d{1,2}:\d{2}\b\s+"
            r"(.+?)\s+-\s+(.+)$",
            text
        )

        if not match:
            continue

        artist = match.group(1).strip()
        title = match.group(2).strip()

        # Vaste programmavermeldingen van OnlineRadioBox negeren.
        # Dit zijn geen echte muzieknummers.
        program_text = f"{artist} {title}".strip().lower()

        if program_text in {
            "studio brussel vuurland",
            "oud - vrt studio brussel vuurland",
            "did you know that there's a tunnel under ocean blvd",
        }:
            continue

        if len(artist) > 150:
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
        remaining = int(SPOTIFY_SEARCH_BLOCKED_UNTIL - time.time())
        raise RuntimeError(f"Spotify Search nog geblokkeerd ({remaining} seconden resterend)")

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

    items = data.get("tracks", {}).get("items", [])

    wanted_title = title.strip().lower()
    wanted_artist = artist.strip().lower()

    for item in items:
        spotify_title = item.get("name", "").strip().lower()
        spotify_artists = [
            a.get("name", "").strip().lower()
            for a in item.get("artists", [])
        ]
        if spotify_title == wanted_title and wanted_artist in spotify_artists:
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
    tracks = get_vuurland_tracks()

    print()
    print(f"   {len(tracks)} nummers gevonden.")

    # ---------------------------------
    # PERSISTENTE WACHTRIJ
    # ---------------------------------
    queue_file = os.path.join(
        DATA_DIR,
        "vuurland_queue.json"
    )

    try:
        with open(queue_file, "r") as f:
            queue = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        queue = []

    if not isinstance(queue, list):
        queue = []

    seen = load_seen()

    # Nieuwe nummers uit Vuurland aan de wachtrij toevoegen.
    queued_keys = {
        f"{item['artist'].strip().lower()}|||"
        f"{item['title'].strip().lower()}"
        for item in queue
        if isinstance(item, dict)
        and "artist" in item
        and "title" in item
    }

    added_to_queue = 0

    for artist, title in tracks:
        key = (
            f"{artist.strip().lower()}|||"
            f"{title.strip().lower()}"
        )

        if key in seen or key in queued_keys:
            continue

        queue.append({
            "artist": artist,
            "title": title
        })
        queued_keys.add(key)
        added_to_queue += 1

    print(
        f"🆕 {added_to_queue} nieuwe nummers aan de wachtrij toegevoegd."
    )

    # ---------------------------------
    # PLAYLIST
    # ---------------------------------
    if not queue:
        with open(queue_file, "w") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        print("ℹ️ Geen nummers te verwerken.")
        return

    playlist_id = get_playlist()

    cache = load_cache()

    processed = []
    new_tracks = []
    remaining_queue = []

    # ---------------------------------
    # VEILIGE SPOTIFY VERWERKING
    #
    # We doen per GitHub-run maximaal
    # 2 nieuwe Spotify Search-requests.
    #
    # Cache-hits kosten geen Search-request.
    # ---------------------------------
    searches_used = 0
    MAX_SEARCHES_PER_RUN = 2

    for item in queue:
        artist = item["artist"]
        title = item["title"]

        key = (
            artist.strip().lower(),
            title.strip().lower()
        )

        cache_key = (
            f"{artist.strip().lower()}|||"
            f"{title.strip().lower()}"
        )

        if cache_key in cache:
            uri = cache[cache_key]
            print(
                f"💾 Cache gebruikt: {artist} - {title}"
            )

        else:
            if searches_used >= MAX_SEARCHES_PER_RUN:
                remaining_queue.append(item)
                continue

            print(
                f"🔎 Spotify zoeken: {artist} - {title}"
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
                remaining_queue.append(item)

                # Alles wat nog niet behandeld is
                # bewaren.
                current_index = queue.index(item)
                remaining_queue.extend(
                    queue[current_index + 1:]
                )
                break

            searches_used += 1

            if uri is not None:
                cache[cache_key] = uri
                save_cache(cache)

        if uri is None:
            # Niet gevonden: niet als "gezien" markeren.
            # Zo kan een volgende run opnieuw proberen.
            remaining_queue.append(item)
            continue

        processed.append(cache_key)
        new_tracks.append(uri)

    # ---------------------------------
    # SPOTIFY PLAYLIST BIJWERKEN
    # ---------------------------------
    if new_tracks:
        add_tracks(
            playlist_id,
            new_tracks
        )

    # ---------------------------------
    # VERWERKTE TRACKS ALS GEZIEN OPSLAAN
    # ---------------------------------
    seen.update(processed)
    save_seen(seen)

    # ---------------------------------
    # WACHTRIJ OPSLAAN
    # ---------------------------------
    with open(queue_file, "w") as f:
        json.dump(
            remaining_queue,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(
        f"✅ {len(new_tracks)} nieuwe "
        f"nummers toegevoegd."
    )
    print(
        f"📋 {len(remaining_queue)} nummers "
        f"blijven in de wachtrij."
    )

    print(
        f"🔎 Spotify Search gebruikt: "
        f"{searches_used}/{MAX_SEARCHES_PER_RUN}"
    )

    if remaining_queue:
        print(
            "⏭️ De rest wordt automatisch "
            "bij volgende controles verwerkt."
        )

# =========================
# START
# =========================

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
