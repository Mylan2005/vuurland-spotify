import base64
import csv
import hashlib
import http.server
import json
import os
import re
import secrets
import tempfile
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
PLAYLIST_ID = os.environ.get("VUURLAND_PLAYLIST_ID", "555lFTvdRswe9ukybmOM8T")

# Bekende artiest-naamswijzigingen.
#
# BELANGRIJK:
# Dit is GEEN vrije fuzzy artiestenmatch.
# Een alias wordt alleen gebruikt wanneer we expliciet weten
# dat het om dezelfde artiest gaat.
#
# De normale titelcontrole blijft volledig actief.
ARTIST_ALIASES = {
    # v101: officiële artiestcredits die RadioBox onder een andere naam toont.
    "hybris": ["Postiljonen"],
    "xymox": ["Clan of Xymox"],
    # Historische artiestennaam: één artiest, twee officiële catalogusnamen.
    "manitoba": ["Caribou"],
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
    "novastar and piet goddaer": ["Novastar"],
    "the gabby pahinui hawaiian band": ["Gabby Pahinui"],

    # Bewezen solo/band catalogusnaam: exacte naam, geen vrije substring.
    "sam roberts": [
        "Sam Roberts Band",
    ],
    # v38: gecontroleerde solo/bandcatalogus van Elvis Costello.
    "elvis costello": ["Elvis Costello & The Attractions"],
    "elvis costello and the attractions": ["Elvis Costello"],

}

SOURCE_URL = "https://onlineradiobox.com/be/vuurland/playlist/?lang=nl"
MELLOW_MIX_SOURCE_URL = "https://onlineradiobox.com/us/paradisemellowmix/playlist/?lang=nl"
BIG_SONIC_HEAVEN_SOURCE_URL = "https://onlineradiobox.com/us/bigsonicheaven/playlist/?lang=nl"
RADIO_X_CHILLED_SOURCE_URL = "https://onlineradiobox.com/uk/radioxchilled/playlist/?lang=nl"
INDIE_SELECT_SOURCE_URL = "https://onlineradiobox.com/de/indieselect/playlist/?lang=nl"
CHAMPIONSHIP_VINYL_SOURCE_URL = "https://onlineradiobox.com/de/championshipvinyl/playlist/?lang=nl"
DARK_EDGE_SOURCE_URL = "https://onlineradiobox.com/ro/darkedge/playlist/?lang=nl"
DREAMPOP_SOURCE_URL = "https://onlineradiobox.com/de/dreampop/playlist/?lang=nl"
RADIO_INDIE_ALTERNATIVE_SOURCE_URL = "https://onlineradiobox.com/de/31alternative/playlist/?lang=nl"
DKFM_EDGE_SOURCE_URL = "https://onlineradiobox.com/ca/dkfmedge/playlist/?lang=nl"
DKFM_SHOEGAZE_SOURCE_URL = "https://onlineradiobox.com/ca/dkfmshoegazeradio/playlist/?lang=nl"
DKFM_CLASSIC_SOURCE_URL = "https://onlineradiobox.com/ca/dkfmclassic/playlist/?lang=nl"

# Zelfde volgorde voor live-queue, lege rondes en eerlijke v97-fallback.
RADIO_SOURCE_ORDER = (
    "vuurland", "mellow_mix", "big_sonic_heaven",
    "radio_x_chilled", "indie_select", "championship_vinyl", "dark_edge",
    "dreampop_radio", "radio_indie_alternative", "dkfm_edge", "dkfm_shoegaze", "dkfm_classic",
)

CHECK_EVERY_SECONDS = 60  # 1 minuut; maximaal één Search en één toevoeging per ronde
SPOTIFY_SEARCH_BLOCKED_UNTIL = 0
# Actual HTTP attempts (including token retries), reset each sync round.
SPOTIFY_SEARCH_HTTP_USED = 0
SPOTIFY_SEARCH_HTTP_LIMIT = 1

# Metadata van de laatst gekozen Spotify Search-kandidaat.
# find_spotify_track() blijft gewoon een URI-string teruggeven,
# zodat bestaande code en regressietests niet veranderen.
LAST_SPOTIFY_MATCH_ISRC = None
LAST_SPOTIFY_MATCH_METADATA = None

DATA_DIR = os.environ.get("VUURLAND_DATA_DIR", os.path.expanduser("~"))
TOKEN_FILE = os.path.join(DATA_DIR, ".vuurland_spotify_token.json")
CACHE_FILE = os.path.join(DATA_DIR, ".vuurland_spotify_cache.json")
SEEN_FILE = os.path.join(DATA_DIR, ".vuurland_seen.json")



def atomic_save_json(path, data, *, indent=2, ensure_ascii=False):
    """Never expose a partially written JSON state file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory,
            prefix=".vuurland-", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            json.dump(data, handle, indent=indent, ensure_ascii=ensure_ascii)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            value = json.load(f)
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Spotify-cache is geen JSON-object; state niet overschrijven")
    return value


def save_cache(cache):
    # spotify_request() writes the 429 cooldown independently of the caller's
    # in-memory cache. Never overwrite a newer, still-active disk cooldown.
    persisted = load_cache()
    now = time.time()
    for key in ("__spotify_api_blocked_until", "__spotify_search_blocked_until", "__spotify_server_error_until"):
        disk_until = float(persisted.get(key, 0) or 0)
        caller_until = float(cache.get(key, 0) or 0)
        if disk_until > now and disk_until > caller_until:
            cache[key] = disk_until
    atomic_save_json(CACHE_FILE, cache, indent=2, ensure_ascii=False)


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            value = json.load(f)
    except FileNotFoundError:
        return set()
    if not isinstance(value, list):
        raise ValueError("Seen-state is geen JSON-lijst; niet overschrijven")
    return set(value)


def save_seen(seen):
    atomic_save_json(SEEN_FILE, sorted(seen), indent=2, ensure_ascii=False)


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
    "playlist-modify-public user-library-modify user-library-read "
    "user-read-private"  # Vereist door Spotify voor GET /search (2026).
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

    global SPOTIFY_SEARCH_HTTP_USED
    is_search = endpoint.split("?", 1)[0].rstrip("/") == "/search"
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

        server_until = float(cache.get("__spotify_server_error_until", 0) or 0)
        if server_until > time.time():
            raise RuntimeError("Spotify tijdelijke serverpauze is nog actief.")

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

        # Count real HTTP calls, not just matcher decisions. Never exceed two
        # Spotify Search HTTP attempts within one sync round, including retries.
        if is_search:
            if SPOTIFY_SEARCH_HTTP_USED >= SPOTIFY_SEARCH_HTTP_LIMIT:
                raise RuntimeError("Spotify Search HTTP-budget (2/2) bereikt; queue blijft bewaard.")
            SPOTIFY_SEARCH_HTTP_USED += 1
            print(f"🌐 Spotify Search HTTP: {SPOTIFY_SEARCH_HTTP_USED}/{SPOTIFY_SEARCH_HTTP_LIMIT}")

        response = requests.request(
            method,
            API_URL + endpoint,
            headers=headers,
            timeout=30,
            **kwargs
        )

        # ---------------------------------
        # SPOTIFY RATE LIMIT / DEVELOPMENT QUOTA (v51.6)
        #
        # Niet onmiddellijk opnieuw proberen: bewaar de cooldown duurzaam,
        # ook als Retry-After slechts enkele seconden is. De runner slaat
        # daarna de state op en stopt met Spotify-aanvragen.
        # ---------------------------------
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                wait = max(1, int(retry_after))
            except (TypeError, ValueError):
                wait = 60

            # Development-quota is niet dezelfde 30-seconden-rate-limit.
            # Bij QUOTA_EXCEEDED niet elke twee minuten opnieuw proberen.
            if "QUOTA_EXCEEDED" in str(getattr(response, "text", "") or "").upper():
                wait = max(wait, 3600)
                print("⏸️ Spotify Development Mode-quota bereikt.")

            cache = load_cache()
            previous = float(cache.get("__spotify_api_blocked_until", 0) or 0)
            blocked_until = max(previous, time.time() + wait + 1)
            cache["__spotify_api_blocked_until"] = blocked_until
            save_cache(cache)
            print(
                f"⏸️ Spotify HTTP 429: cooldown {wait} seconden duurzaam "
                "opgeslagen; geen onmiddellijke retry."
            )
            raise RuntimeError(
                "Spotify 429: cooldown bewaard; deze sync-run stopt veilig."
            )

        # ---------------------------------
        # TIJDELIJKE SERVERFOUTEN
        # ---------------------------------
        if response.status_code in (500, 502, 503, 504):
            if is_search:
                # A 5xx is a temporary server outage, NOT a missing track or
                # a 429. Pause Spotify for three minutes and keep RadioBox live.
                cache = load_cache()
                cache["__spotify_server_error_until"] = max(
                    float(cache.get("__spotify_server_error_until", 0) or 0),
                    time.time() + 180,
                )
                save_cache(cache)
                print("⏸️ Spotify-serverfout: 180 seconden pauze; radiocontrole blijft actief.")
                raise RuntimeError(
                    f"Spotify Search HTTP {response.status_code}: tijdelijke serverfout; "
                    "nummer blijft in de wachtrij, geen mislukte match."
                )
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

        # v73: HTTP 403 is geen ontbrekend lied en geen 429.
        # Log alleen een beperkte Spotify-foutomschrijving; nooit tokens.
        # Bewaar een Spotify-only cooldown en houd de radioqueue intact.
        if response.status_code == 403:
            explanation = ""
            try:
                detail = response.json().get("error", {})
                if isinstance(detail, dict):
                    explanation = str(detail.get("message", ""))[:160]
            except (ValueError, TypeError, AttributeError):
                pass
            print(f"🚫 Spotify HTTP 403 op {endpoint.split('?', 1)[0]}"
                  + (f": {explanation}" if explanation else ""))
            cache = load_cache()
            cache["__spotify_server_error_until"] = max(
                float(cache.get("__spotify_server_error_until", 0) or 0),
                time.time() + 3600,
            )
            save_cache(cache)
            raise RuntimeError(
                "Spotify HTTP 403: toegangsweigering; 60 minuten "
                "Spotify-pauze, radiowachtrij bewaren."
            )

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

            if is_search:
                if SPOTIFY_SEARCH_HTTP_USED >= SPOTIFY_SEARCH_HTTP_LIMIT:
                    raise RuntimeError("Spotify Search HTTP-budget (2/2) bereikt na tokenvernieuwing.")
                SPOTIFY_SEARCH_HTTP_USED += 1
                print(f"🌐 Spotify Search HTTP: {SPOTIFY_SEARCH_HTTP_USED}/{SPOTIFY_SEARCH_HTTP_LIMIT} (tokenretry)")

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

# === VUURLAND AUTO VOLUMES v1 ===
VOLUME_LIMIT = 10000
VOLUME_NAME_PREFIX = "🔥 Vol "
VOLUME_EXACT_COUNT_GUARD = 10
PENDING_LIBRARY_LIKE_RETRY_SECONDS = 3600


def _get_playlist_total(playlist_id):
    data = spotify_request(
        "GET",
        f"/playlists/{playlist_id}/items",
        params={"limit": 1, "offset": 0},
    )
    try:
        return int(data.get("total", 0))
    except (TypeError, ValueError):
        return 0


def _find_named_playlist(playlist_name):
    offset = 0
    while True:
        data = spotify_request(
            "GET", "/me/playlists", params={"limit": 50, "offset": offset}
        )
        items = data.get("items", []) or []
        for item in items:
            if str(item.get("name") or "") == playlist_name:
                playlist_id = str(item.get("id") or "").strip()
                if playlist_id:
                    return playlist_id
        if not data.get("next"):
            return None
        offset += len(items) or 50


def _create_volume_playlist(volume_number):
    playlist_name = f"{VOLUME_NAME_PREFIX}{volume_number}"
    data = spotify_request(
        "POST",
        "/me/playlists",
        json={
            "name": playlist_name,
            "public": False,
            "description": "Automatisch vervolg van de Vuurland Spotify-sync.",
        },
    )
    playlist_id = str(data.get("id") or "").strip()
    if not playlist_id:
        raise RuntimeError(f"Spotify gaf geen playlist-ID terug voor {playlist_name}.")
    print(f"🆕 Nieuwe Spotify-playlist aangemaakt: {playlist_name}")
    return playlist_id


# === v129 SAFE MULTI-VOLUME DEDUPE RECOVERY ===
def v129_restore_volume_dedupe(cache, active_volume_number):
    """Fail closed when completed volumes are not covered by the shared cache.

    Never publish partial rebuilds. Reads use the existing Spotify request wrapper,
    including its persistent 429 handling. No Spotify writes are performed.
    """
    if active_volume_number < 2:
        return False
    mapping = dict(cache.get("__vuurland_volume_playlists") or {})
    mapping["1"] = PLAYLIST_ID
    expected = [str(n) for n in range(1, active_volume_number + 1)]
    if any(not mapping.get(n) for n in expected):
        raise RuntimeError("v129: volume-ID ontbreekt; geen Spotify-toevoegingen")
    known_uris = cache.get("__playlist_uris")
    known_keys = cache.get("__playlist_keys")
    known_isrc = cache.get("__playlist_isrcs")
    minimum = VOLUME_LIMIT * (active_volume_number - 1)
    if (cache.get("__playlist_isrc_cache_ready") is True
            and isinstance(known_uris, list)
            and isinstance(known_keys, list)
            and isinstance(known_isrc, list)
            and len(set(known_uris)) >= minimum):
        return False
    print("🛡️ v129: onvolledige volume-cache; alle volumes veilig opnieuw lezen.")
    new_uris, new_isrcs, new_keys, new_uri_isrc = set(), set(), set(), {}
    for number in expected:
        playlist_id = mapping[number]
        offset = 0
        while True:
            data = spotify_request("GET", f"/playlists/{playlist_id}/items",
                                   params={"limit": 50, "offset": offset})
            batch = data.get("items")
            total = data.get("total")
            if not isinstance(batch, list) or not isinstance(total, int) or total < 0:
                raise RuntimeError("v129: ongeldige Spotify-pagina; herstel gestopt")
            for entry in batch:
                track = (entry or {}).get("item")
                if not isinstance(track, dict):
                    continue
                uri = track.get("uri")
                if not uri:
                    continue
                new_uris.add(uri)
                code = str((track.get("external_ids") or {}).get("isrc") or "").strip().upper()
                if code:
                    new_isrcs.add(code)
                    new_uri_isrc[uri] = code
                new_keys.update(make_playlist_keys(track))
                title = normalize_match(track.get("name", ""))
                if title:
                    for artist in track.get("artists", []) or []:
                        name = normalize_match((artist or {}).get("name", ""))
                        if name:
                            new_keys.add(f"{name}|||{title}")
            offset += len(batch)
            if offset >= total:
                break
            if not batch:
                raise RuntimeError("v129: onvolledige Spotify-paginering; herstel gestopt")
    if len(new_uris) < minimum:
        raise RuntimeError("v129: volume-herstel onvolledig; cache onveranderd")
    # Atomic swap only after all volumes have been read successfully.
    cache["__playlist_uris"] = sorted(new_uris)
    cache["__playlist_isrcs"] = sorted(new_isrcs)
    cache["__playlist_keys"] = sorted(new_keys)
    cache["__spotify_uri_isrc"] = new_uri_isrc
    cache["__playlist_isrc_cache_ready"] = True
    cache["__playlist_cache_time"] = int(time.time())
    save_cache(cache)
    print(f"✅ v129: {len(new_uris)} Spotify-tracks uit {len(expected)} volumes hersteld.")
    return True

def get_active_volume_playlist(cache):
    volume_playlists = dict(cache.get("__vuurland_volume_playlists", {}))
    volume_playlists.setdefault("1", PLAYLIST_ID)

    try:
        volume_number = int(cache.get("__vuurland_active_volume", 1))
    except (TypeError, ValueError):
        volume_number = 1
    volume_number = max(1, volume_number)

    playlist_id = volume_playlists.get(str(volume_number)) or PLAYLIST_ID
    cached_playlist_id = cache.get("__vuurland_active_playlist_id")
    cached_count = cache.get("__vuurland_active_playlist_count")

    if (
        cached_playlist_id != playlist_id
        or not isinstance(cached_count, int)
        or cached_count < 0
    ):
        cached_count = _get_playlist_total(playlist_id)

    while cached_count >= VOLUME_LIMIT:
        next_volume = volume_number + 1
        next_key = str(next_volume)
        next_name = f"{VOLUME_NAME_PREFIX}{next_volume}"

        next_playlist_id = volume_playlists.get(next_key)
        if not next_playlist_id:
            next_playlist_id = _find_named_playlist(next_name)

        if next_playlist_id:
            next_count = _get_playlist_total(next_playlist_id)
        else:
            next_playlist_id = _create_volume_playlist(next_volume)
            next_count = 0

        volume_playlists[next_key] = next_playlist_id
        volume_number = next_volume
        playlist_id = next_playlist_id
        cached_count = next_count

    cache["__vuurland_volume_playlists"] = volume_playlists
    cache["__vuurland_active_volume"] = volume_number
    cache["__vuurland_active_playlist_id"] = playlist_id
    cache["__vuurland_active_playlist_count"] = cached_count
    save_cache(cache)
    return playlist_id, volume_number, cached_count


def save_track_to_library(uri):
    if not uri:
        return
    spotify_request("PUT", "/me/library", params={"uris": uri})


def _attempt_library_like(cache, uri):
    pending = dict(cache.get("__pending_library_likes", {}))
    pending[uri] = {"last_attempt": 0}
    cache["__pending_library_likes"] = pending
    save_cache(cache)

    try:
        save_track_to_library(uri)
    except Exception as error:
        pending = dict(cache.get("__pending_library_likes", {}))
        pending[uri] = {
            "last_attempt": int(time.time()),
            "error": str(error)[:300],
        }
        cache["__pending_library_likes"] = pending
        save_cache(cache)
        print("⚠️ Track staat in het volume, maar kon nog niet worden geliket; veilig pending.")
        print(f"   {error}")
        return False

    pending = dict(cache.get("__pending_library_likes", {}))
    pending.pop(uri, None)
    cache["__pending_library_likes"] = pending
    save_cache(cache)
    print("❤️ Opgeslagen in Liked Songs.")
    return True


# === VUURLAND PENDING LIKES RETRY v1 ===
def _retry_one_pending_library_like(cache):
    pending = dict(cache.get("__pending_library_likes", {}))
    if not pending:
        return False

    now = int(time.time())

    for uri, info in pending.items():
        info = dict(info or {})
        last_attempt = int(info.get("last_attempt", 0) or 0)

        if (
            last_attempt
            and now - last_attempt
            < PENDING_LIBRARY_LIKE_RETRY_SECONDS
        ):
            continue

        try:
            save_track_to_library(uri)
        except Exception as error:
            info["last_attempt"] = now
            info["error"] = str(error)[:300]
            pending[uri] = info
            cache["__pending_library_likes"] = pending
            save_cache(cache)
            print(
                "⚠️ Pending Liked Songs retry mislukt; "
                "volgende poging pas na cooldown."
            )
            return False

        pending.pop(uri, None)
        cache["__pending_library_likes"] = pending
        save_cache(cache)
        print(
            "❤️ Eerder pending nummer alsnog opgeslagen "
            "in Liked Songs."
        )
        return True

    return False


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


def get_big_sonic_heaven_tracks():
    return get_radiobox_tracks(
        BIG_SONIC_HEAVEN_SOURCE_URL,
        "Big Sonic Heaven Radio",
        {"big sonic heaven radio"},
    )


def get_radio_x_chilled_tracks():
    return get_radiobox_tracks(RADIO_X_CHILLED_SOURCE_URL, "Radio X Chilled")


def get_indie_select_tracks():
    return get_radiobox_tracks(INDIE_SELECT_SOURCE_URL, "Indie Select")


def get_championship_vinyl_tracks():
    return get_radiobox_tracks(CHAMPIONSHIP_VINYL_SOURCE_URL, "Championship Vinyl")


def get_dark_edge_tracks():
    # RadioBox toont deze identieke zenderjingle honderden keren.
    # Zonder program_labels zou de matcher hem zien als artiest - titel.
    return get_radiobox_tracks(
        DARK_EDGE_SOURCE_URL,
        "Dark Edge Radio",
        {"dark edge radio - soft alternative/indie music"},
    )


def get_dreampop_radio_tracks():
    return get_radiobox_tracks(
        DREAMPOP_SOURCE_URL,
        "Dreampop Radio",
    )


def get_radio_indie_alternative_tracks():
    # Exacte zenderjingles blokkeren vóór de Spotify-matcher en wachtrij.
    return get_radiobox_tracks(
        RADIO_INDIE_ALTERNATIVE_SOURCE_URL,
        "Radio Indie Alternative",
        {
            "alternative radio - jingle1",
            "alternative radio - jingle2",
        },
    )


# v128: enkel expliciete DKFM EDGE-station announcements blokkeren.
def get_dkfm_edge_tracks():
    raw = get_radiobox_tracks(
        DKFM_EDGE_SOURCE_URL,
        "DKFM Edge",
        {"dkfm edge"},
    )
    clean = []
    removed = 0
    for artist, title in raw:
        # Het station schrijft jingles als "DKFM EDGE" of
        # "DKFM EDGE - Tested Daily" / "DKFM EDGE - Fully Stocked".
        # Filter uitsluitend deze zenderidentiteit, niet muziekgenres.
        if re.match(r"^dkfm\s+edge(?:\b|\s*[-:])", str(artist).strip(), re.I):
            removed += 1
            continue
        clean.append((artist, title))
    if removed:
        print(f"⏭️ DKFM Edge: {removed} stationjingle(s) genegeerd.")
    return clean

# v130: DKFM Shoegaze Radio als elfde bron. Alleen expliciete station-IDs.
def get_dkfm_shoegaze_tracks():
    raw = get_radiobox_tracks(
        DKFM_SHOEGAZE_SOURCE_URL,
        "DKFM Shoegaze Radio",
        {"id/psa - id/psa", "dkfm shoegaze radio"},
    )
    clean = []
    removed = 0
    for artist, title in raw:
        artist_clean = str(artist).strip().casefold()
        title_clean = str(title).strip().casefold()
        if (artist_clean in ("id/psa", "dkfm", "dkfm shoegaze radio")
                or (artist_clean == "id" and title_clean == "psa")):
            removed += 1
            continue
        clean.append((artist, title))
    if removed:
        print(f"⏭️ DKFM Shoegaze Radio: {removed} stationjingle(s) genegeerd.")
    return clean

# v137: DKFM Classic als twaalfde bron; alleen station-identificaties weren.
def get_dkfm_classic_tracks():
    raw = get_radiobox_tracks(
        DKFM_CLASSIC_SOURCE_URL,
        "DKFM Classic",
        {"dkfm classic"},
    )
    clean = []
    removed = 0
    for artist, title in raw:
        a = str(artist).strip()
        t = str(title).strip()
        if (a.casefold() == "dkfm" and
                re.match(r"^dkfm\s+classic\s+ident(?:\b|\s*[-:#])", t, re.I)) or (
                a.casefold() == "dkfm classic" and
                re.match(r"^(?:ident|station\s+id)(?:\b|\s*[-:#])", t, re.I)):
            removed += 1
            continue
        clean.append((artist, title))
    if removed:
        print(f"⏭️ DKFM Classic: {removed} stationjingle(s) genegeerd.")
    return clean

# v119: Duitse numMERTITELS, niet Duitse artiesten, blokkeren.
# Herkenning gebeurt op TITEL, niet op artiestennaam of radioland.
# Bij twijfel nooit een Engelse titel blokkeren wegens de nationaliteit.
V119_GERMAN_TITLES = frozenset({
    "weil das morgen noch so ist", "ich muss gar nix", "ich muß gar nix",
    "ein song reicht", "die bomben meiner stadt",
    "zum laichen und sterben ziehen die lachse den fluss hinauf",
    "die schonheit der chance", "die schönheit der chance",
    "nicht atmen", "der elektrische reiter", "dialog mit dem tolpel",
    "wie kann es sein", "ich tauche auf", "neuer morgen",
    "wir waren jung und wir brauchten das geld",
    "wahre arbeit wahrer lohn", "bis ans ende der welt",
    "mama schickt mich", "begrab mein herz",
    "die transsylvanische verwandte ist da", "auch ein guter sommer",
    "jonny du lump", "lied vom ende des kapitalismus",
    "die große sporadische", "das ende der beschwerde",
    "keine bewegung", "die toten auf dem rücksitz",
})


def v119_title_normalize(value):
    import re
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ß", "ss")
    # Live/remix-aanduidingen mogen Duitse basistitels niet verbergen.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^\wäöü]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def v119_is_german_title(title):
    import re
    text = v119_title_normalize(title)
    if not text:
        return False
    if text in V119_GERMAN_TITLES:
        return True
    # Gecontroleerde basistitels met live/remix/toevoegingen.
    if any(text.startswith(base + " ") for base in V119_GERMAN_TITLES if len(base) >= 13):
        return True
    # Duitse zinsdelen die voldoende onderscheidend zijn.
    patterns = (
        r"\bweil\s+(?:das|ich|du|wir|sie)\b",
        r"\b(?:ich|wir|du)\s+(?:bin|habe|hab|will|muss|musst|waren|brauchen|brauchten|tauche|liebe)\b",
        r"\b(?:nicht|kein|keine|keinen)\s+(?:atmen|mehr|bewegung|zeit|angst|liebe)\b",
        r"\b(?:wie|was|wer|warum)\s+(?:kann|ist|soll|sind|wird|geht|macht)\b",
        r"\b(?:zum|zur)\s+(?:laichen|sterben|welt|sonne|hölle|hoelle)\b",
        r"\b(?:meiner|meinem|meinen|deiner|deinem|deinen)\s+\w+\b",
        r"\b(?:der|die|das)\s+(?:elektrische|schonheit|schönheit|bomben|toten|ende|transsylvanische|große|grosse)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


# v102: Duitse ZANG uitsluiten, niet Duitse titels of artiesten.
# Alleen gecontroleerde opnames. Geen automatische taalherkenning op metadata.
GERMAN_VOCAL_RADIO_TRACKS = frozenset({
    ("thees uhlmann", "zum laichen und sterben ziehen die lachse den fluss hinauf"),
    ("thees uhlmann", "zum laichen und sterben ziehen die lachse den fluss hinauf live gf36"),

    ("tomte", "die schönheit der chance"),
    ("tomte", "die schonheit der chance"),
})
GERMAN_VOCAL_SPOTIFY_IDS = frozenset({
    "1j10uvA0XYl6TNNyY7XqGm",  # Door gebruiker bevestigde Duitse zang.
})


def is_confirmed_german_vocal(artist, title):
    return (" ".join(str(artist).casefold().split()),
            " ".join(str(title).casefold().split())) in GERMAN_VOCAL_RADIO_TRACKS


def is_blocked_german_spotify_uri(uri):
    return str(uri or "").rsplit(":", 1)[-1] in GERMAN_VOCAL_SPOTIFY_IDS


# v106: fail-closed taalcontrole voor nieuwe radio-items.
# Onbekende taal = wachten op beslissing; geen gok op basis van artiest of titel.
def v106_language_decision(artist, title):
    import csv
    from pathlib import Path

    key = (" ".join(str(artist).casefold().split()),
           " ".join(str(title).casefold().split()))
    decisions_path = Path("vuurland_taalbeslissingen.csv")
    pending_path = Path("vuurland_taalcontrole_nieuw.csv")

    if is_confirmed_german_vocal(artist, title):
        return "block"

    if decisions_path.exists():
        with decisions_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row_key = (" ".join(str(row.get("artist", "")).casefold().split()),
                           " ".join(str(row.get("title", "")).casefold().split()))
                if row_key != key:
                    continue
                status = str(row.get("beslissing", "")).strip().casefold()
                if status in ("toestaan", "allow", "ok"):
                    return "allow"
                if status in ("blokkeren", "block", "duits"):
                    return "block"
                return "review"

    existing = set()
    if pending_path.exists():
        with pending_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                existing.add((" ".join(str(row.get("artist", "")).casefold().split()),
                              " ".join(str(row.get("title", "")).casefold().split())))
    if key not in existing:
        with pending_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            if pending_path.stat().st_size == 0:
                writer.writerow(["artist", "title"])
            writer.writerow([artist, title])
    return "review"


# v113: gecontroleerde niet-Duitse artiesten (exacte naam, geen fuzzy match).
# Alleen de expliciet genoemde acts: niet op woorddelen of muziekstijl gokken.
# Een bestaande MusicBrainz-blokkering krijgt altijd voorrang.
V113_VERIFIED_NON_GERMAN_ARTISTS = {
    'arctic monkeys': 'GB',
    'beady eye': 'GB',
    'biffy clyro': 'GB',
    'blink-182': 'US',
    'blonde redhead': 'US',
    'bombay bicycle club': 'GB',
    'brian eno': 'GB',
    'david bowie': 'GB',
    'david gray': 'GB',
    "dma's": 'AU',
    'elliott smith': 'US',
    'gorillaz': 'GB',
    "guns n' roses": 'US',
    'hozier': 'IE',
    'inhaler': 'IE',
    'jamie t': 'GB',
    'lisa gerrard': 'AU',
    'lorde': 'NZ',
    'maximo park': 'GB',
    'metallica': 'US',
    'mumford & sons': 'GB',
    'nick cave & the bad seeds': 'AU',
    'noel gallagher': 'GB',
    'paolo nutini': 'GB',
    'paramore': 'US',
    'peter bjorn and john': 'SE',
    'pj harvey': 'GB',
    'r.e.m.': 'US',
    'red hot chili peppers': 'US',
    'richard ashcroft': 'GB',
    'sam fender': 'GB',
    'slowdive': 'GB',
    'suede': 'GB',
    'the beatles': 'GB',
    'the church': 'AU',
    'the coral': 'GB',
    'the cranberries': 'IE',
    'the cure': 'GB',
    'the flaming lips': 'US',
    'the horrors': 'GB',
    'the jam': 'GB',
    'the lathums': 'GB',
    'the maccabees': 'GB',
    'the rolling stones': 'GB',
    'the temper trap': 'AU',
    'the verve': 'GB',
}


# v108: artiesten uit Duitsland blokkeren via MusicBrainz.
# Dit filtert op artiest-land, NIET op zangtaal. Ook Engelse zang en
# instrumentale tracks van Duitse artiesten worden dus geblokkeerd.
# Eén MusicBrainz-opzoeking per >=60 seconden, cache in bestaande Spotify-state.
def v108_artist_country_decision(artist, cache):
    import urllib.parse
    import time
    import requests
    import unicodedata

    def norm(value):
        value = unicodedata.normalize("NFKD", str(value).casefold())
        return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())

    artist_name = str(artist).strip()
    key = norm(artist_name)
    if not key:
        return "unknown"

    state = cache.setdefault("__v108_musicbrainz_artists", {})
    now = time.time()
    saved = state.get(key)
    # v118: onbekende artiestenherkomst is GEEN toestemming.
    # Bevestigde Duitse band; normalisatie maakt Groß/Gross schrijfvarianten gelijk
    # waar de umlaut verschilt. Ook vóór de MusicBrainz-cooldown blokkeren.
    if key in {"großstadtgefluster", "grossstadtgefluster", "grossstadtgefluester",
               "großstadtgefluester"}:
        return "block"
    # v113: een bestaande Duitse artiestenblokkering nooit omzeilen.
    if isinstance(saved, dict) and saved.get("decision") == "block":
        return "block"
    # v113: deze exact geïdentificeerde niet-Duitse acts hoeven niet op een
    # MusicBrainz-storing te wachten. Spotify-match/versie/duplicates blijven
    # volledig door de bestaande controles gaan.
    if key in V113_VERIFIED_NON_GERMAN_ARTISTS:
        return "allow"
    if isinstance(saved, dict) and float(saved.get("until", 0) or 0) > now:
        return saved.get("decision", "unknown")

    # v118: tijdens MusicBrainz-cooldown geen nieuwe MusicBrainz HTTP-call.
    # 'unknown' wordt door de aanroeper veilig in de wachtrij gehouden.
    next_at = float(cache.get("__v108_musicbrainz_next_lookup_at", 0) or 0)
    if now < next_at:
        return "unknown"

    # Bewaar de cooldown VÓÓR de HTTP-call; ook een fout telt als poging.
    cache["__v108_musicbrainz_next_lookup_at"] = now + 60
    save_cache(cache)
    try:
        # Een exact gequote artiestennaam voorkomt een zoekopdracht op losse woorden.
        quoted = artist_name.replace("\\", " ").replace('"', " ")
        query = 'artist:"' + quoted + '"'
        response = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": query, "fmt": "json", "limit": 10},
            headers={"User-Agent": "VuurlandSpotifySync/108 (https://github.com/Mylan2005/vuurland-spotify)",
                     "Accept": "application/json"},
            timeout=(4, 15),  # connect 4 s; trage MusicBrainz-read tot 15 s
        )
        response.raise_for_status()
        results = response.json().get("artists", [])
    except (requests.RequestException, ValueError) as exc:
        # v117: adaptieve MusicBrainz-cooldown; respecteer HTTP 429/503
        # en Retry-After, zonder onbekende artiesten uit Spotify te houden.
        # Bij onzekere herkomst is Duitse afkomst niet gegarandeerd uitgesloten.
        # v112: adaptieve MusicBrainz-cooldown
        response_error = getattr(exc, "response", None)
        status = getattr(response_error, "status_code", None)
        delay = 300 if status in (429, 503) else 60
        if status in (429, 503) and response_error is not None:
            retry_after = response_error.headers.get("Retry-After", "")
            try:
                delay = max(delay, min(86400, int(float(retry_after))))
            except (TypeError, ValueError):
                pass
        print(f"⚠️ MusicBrainz tijdelijk onbereikbaar voor {artist_name}: "
              f"{type(exc).__name__} (HTTP {status or 'onbekend'}); "
              f"volgende poging na minstens {delay} seconden.")
        retry_at = time.time() + delay
        cache["__v108_musicbrainz_next_lookup_at"] = retry_at
        # v117: HTTP 429 blijft volledig gerespecteerd: niet opnieuw
        # MusicBrainz raadplegen vóór retry_at. De radioqueue gaat WEL door.
        # Ook bij 503/netwerkfouten geldt dit. Bekende DE-blokkades blijven.
        if status != 429:
            cache["__v115_musicbrainz_outage_until"] = retry_at
        print("⏳ v118: MusicBrainz-cooldown actief; onbekende artiesten "
              "blijven veilig in de wachtrij en gaan NIET naar Spotify.")
        save_cache(cache)
        return "unknown"

    matches = [r for r in results if norm(r.get("name", "")) == key
               and int(r.get("score", 0) or 0) >= 95]
    countries = {str(r.get("country", "")).upper() for r in matches if r.get("country")}
    # Alleen DE blokkeren als de naam eenduidig is: bij meerdere landen
    # is een artiestennaam onvoldoende om de juiste act te identificeren.
    if countries == {"DE"}:
        decision = "block"
    elif countries and "DE" not in countries:
        decision = "allow"
    else:
        decision = "unknown"

    # Onbekende/ambigue artiesten korter cachen; later opnieuw beoordelen.
    ttl = 7 * 86400 if decision == "unknown" else 90 * 86400
    state[key] = {"decision": decision, "until": now + ttl,
                  "countries": sorted(countries)}
    save_cache(cache)
    return decision


# v110: bekende fout in artiestentag van Indie Select.
# Alleen exact "M8310" (niet andere M83-achtige artiestennamen).
def v110_correct_radio_artist(artist, source):
    if str(source).strip().casefold() == "indie_select" and str(artist).strip().casefold() == "m8310":
        return "M83"
    return artist


# =========================
# NUMMER ZOEKEN
# =========================

def _numbered_title_equivalent(value):
    """Veilige catalogusnummering: Untitled I / Untitled #1 / Untitled 1.

    Alleen de generieke genummerde compositietitels; geen vrije
    Romeins-naar-Arabisch-conversie van gewone songtitels.
    """
    raw = str(value or "").strip()
    match = re.fullmatch(
        r"(?i)(untitled|part|movement|track)\s+(?:#\s*|no\.?\s*)?([ivx]+|\d{1,2})",
        raw,
    )
    if not match:
        return raw
    word, ordinal = match.groups()
    values = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
              "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
    numeric = int(ordinal) if ordinal.isdigit() else values.get(ordinal.upper())
    if numeric is None or not 1 <= numeric <= 10:
        return raw
    return f"{word} {numeric}"



# === v98: algemene metadata-equivalenties, nooit autorisatie op track-ID ===
def v98_credit_identity(value):
    """Exacte creditidentiteit met veilige parenthetische transliteratie.

    Een artiest kan bij Spotify een naam in een ander schrift gebruiken
    met de RadioBox-naam expliciet tussen haakjes. Geen fuzzy transliteratie.
    """
    raw = str(value or '').strip()
    import unicodedata
    raw = unicodedata.normalize('NFKD', raw.casefold().replace('&', ' and '))
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return ''.join(c for c in raw if c.isalnum())


def v98_exact_collaboration(radio_credit, spotify_names):
    """Volledige meerdere artiesten, ongeacht volgorde, zonder ontbrekende gasten.

    Alleen actief als Spotify 2+ losse artist objects geeft. Splits geen
    gewone bandnamen naar willekeurige zelfstandige solo-opnames.
    """
    if len(spotify_names) < 2:
        return False
    radio = str(radio_credit or '').strip()
    # `A, B & C`, `A, B and C`, `A and B` en `A & B`.
    pieces = re.split(r'\s*,\s*|\s+(?:&|and)\s+', radio, flags=re.I)
    pieces = [p.strip().lstrip('& ').strip() for p in pieces if p.strip().lstrip('& ').strip()]
    expected = [v98_credit_identity(x) for x in pieces]
    actual = [v98_credit_identity(x) for x in spotify_names]
    if (len(expected) == len(actual) and len(set(expected)) == len(expected)
            and sorted(expected) == sorted(actual)):
        return True
    # Bandnamen kunnen zelf `&` bevatten: `Iron & Wine and Calexico`.
    # Test daarom ook exacte volledige Spotify-namen, in elke volgorde,
    # zonder die bandnaam ooit tot `Iron` en `Wine` te reduceren.
    if 2 <= len(spotify_names) <= 4:
        import itertools
        wanted = v98_credit_identity(radio_credit)
        for permutation in itertools.permutations(spotify_names):
            for separator in (' and ', ' & ', ', ', ', '):
                if v98_credit_identity(separator.join(permutation)) == wanted:
                    return True
    return False


def v98_parenthetical_artist_alias(radio_artist, spotify_artist):
    """Alleen letterlijk vermelde volledige naam in Spotify-haakjes."""
    radio_key = v98_credit_identity(radio_artist)
    spotify_text = str(spotify_artist or '')
    return bool(radio_key and any(
        v98_credit_identity(part) == radio_key
        for part in re.findall(r'\(([^()]+)\)', spotify_text)
    ))


def v98_classical_movement_key(value):
    """Voorzichtig werk+deel, zonder uitvoerder uit radiometadata af te leiden."""
    s = str(value or '').casefold()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    words = set(s.split())
    # Alleen specifieke bekende structuur: Four Seasons / Summer / movement I.
    # Geen naam-/ID-exceptie, wel volledige compositie- en bewegingstoets.
    seasons = ('four seasons' in s or '4 seasons' in s)
    summer = 'summer' in words
    movement = ('allegro non molto' in s or 'allegro non moto' in s)
    if seasons and summer and movement:
        return ('four seasons', 'summer', 'i', 'allegro non molto')
    return None


def v98_classical_composer_in_title(radio_composer, spotify_title):
    """Componist in werkmetadata, terwijl Spotify alleen uitvoerders crediteert.

    Vereis de volledige achternaam als afzonderlijk woord in de officiële
    titel. Dit geeft uitsluitend een artiestbewijs voor een al exact
    geïdentificeerd klassiek werk en deel, nooit voor een los nummer.
    """
    name = str(radio_composer or '').strip().casefold().split()
    if len(name) < 2 or len(name[-1]) < 5:
        return False
    return bool(re.search(r'(?<!\w)' + re.escape(name[-1]) + r'(?!\w)',
                          str(spotify_title or '').casefold()))


# === v80: conservatieve cataloguskennis (geen extra Spotify-requests) ===
def v80_unicode_search_text(value):
    """Veilige zoek-Schrijfwijze: behoud alle betekenisvolle woorden/cijfers."""
    import unicodedata
    text = str(value or '').translate(str.maketrans({
        'ʻ': "'", 'ʼ': "'", '’': "'", '‘': "'", '＇': "'",
        'æ': 'ae', 'Æ': 'Ae', 'œ': 'oe', 'Œ': 'Oe', 'ø': 'o', 'Ø': 'O', 'ß': 'ss',
        'ﬁ': 'fi', 'ﬂ': 'fl',
    }))
    text = unicodedata.normalize('NFKC', text)
    return ' '.join(text.split())


def v80_search_route(artist, title, variant, confirmed=None):
    """Herbruikbare zoekroute. Onzekerheid leidt NOOIT tot automatische match."""
    title = v80_unicode_search_text(title)
    artist = v80_unicode_search_text(artist)
    if confirmed and confirmed.get('title') and confirmed.get('artist'):
        # Alleen eerder gevalideerde artiest/titel; validatie blijft verplicht.
        return {'title': confirmed['title'], 'artist': confirmed['artist'], 'reason': 'confirmed_catalog_spellings'}
    # v89: afwijkende zoekroute bij gewone woorden in gemiste radiotitels.
    # De vorige strategie maakte van "Lullaby" bijvoorbeeld "L U L L A B Y".
    # Dit was geen officiële catalogustitel. Houd de normale woorden intact.
    if variant == 1 and artist.casefold().strip() == "pieta brown" and title.casefold().strip() == "lullaby":
        return {'title': title, 'artist': artist, 'reason': 'v89_preserve_title'}
    if variant == 1 and re.fullmatch(r'[A-Za-z]{6,16}', title):
        return {'title': ' '.join(title.upper()), 'artist': artist, 'reason': 'spaced_letters'}
    return {'title': title, 'artist': artist, 'reason': 'ordinary'}


def v80_record_confirmed(cache, artist, title, spotify_artist, spotify_title, uri):
    """Onthoud een veilige zoekhint alleen na gekozen match, zonder URI-autorisatie."""
    if not uri or not str(uri).startswith('spotify:track:'):
        return False
    key = _v47_key(artist, title)
    learned = cache.setdefault('__v80_confirmed_spellings', {})
    if not isinstance(learned, dict):
        return False
    # Vaste limiet tegen onbeperkte groei; geen ongecontroleerd model-leren.
    if key not in learned and len(learned) >= 2000:
        return False
    learned[key] = {'artist': str(spotify_artist)[:160], 'title': str(spotify_title)[:320]}
    return True


def v80_failure_reason(items, artist, title):
    """Verklarende diagnose; nooit zelfstandig beslissen dat iets matcht."""
    if not items:
        return 'no_results'
    if any(not x.get('is_playable', True) for x in items):
        return 'includes_unplayable_candidates'
    wanted = normalize_match(artist)
    names = [normalize_match(a.get('name', '')) for x in items for a in x.get('artists', [])]
    if wanted and wanted not in names:
        return 'artist_credit_or_search_ranking'
    return 'title_version_or_ambiguity'

# v101: bevestigde catalogus-ID's blijven locators: GET + dezelfde matcher,
# nooit blind toevoegen. Deze exacte bronregels verbruiken GEEN Spotify Search.
V101_VERIFIED_CATALOG_TRACKS = {
    ("hybris", "how can our love be blind"): "0tAO41U8SChmfAZaehIhuy",
    ("noah & the whale", "five years time"): "12je8giC2S9smUHJ81tpiL",
    ("the kooks", "naive (live for radio x)"): "7BHPGtpuuWWsvE7cCaMuEU",
    ("zbigniew preisner & lisa gerrard", "believe in yourself"): "13w23mzuktOwHzdKqtOYYV",
    ("hybris", "blood flow"): "31Rl9OwQxiRk2T66rqfJfJ",
    ("josefin öhrn & the liberation", "rushing through my mind (mang dynasty extended version)"): "2O5iXIhZbnusoU8au9gast",
    ("the flaming lips", "do you realise?"): "1GjpSlPPKzrCFD0n8Zjhp3",
    ("xymox", "imagination"): "6YVKkyrX3PkBcr5AaxrCWw",
    ("anna domino", "rhythm"): "3599axkmRnbvIAGOzV0uch",
    ("giovanni battista pergolesi", "stabat mater dolorosa"): "7LcypCVM2DeybABIv1Ydaa",
}

# Een door de gebruiker expliciet uitgesloten opname wordt niet gezocht,
# niet uit cache hersteld en niet aan de playlist toegevoegd.
V101_EXCLUDED_RADIO_TRACKS = {
    ("nick cave", "evil ('silver alert' remix feat. matt berninger)"),
    ("kelley polar", "entropy reigns (pearson and usher's second law dynamix)"),
    # v132: persoonlijk uitgesloten Spotify-track 3RnnKPZTVu639oOZ5Qry5y
    ('dj vadim', 'your revolution'),
    ('dj vadim & sarah jones', 'your revolution'),
    ('dj vadim feat. sarah jones', 'your revolution'),
    ('dj vadim featuring sarah jones', 'your revolution'),
    ('sarah jones', 'your revolution'),
    # v135: persoonlijk uitgesloten Spotify-track 72Q9SbemyeHRt8HuLzfCyC
    ('em', "it's not safe to turn off your computer"),
    ('silent strike', "it's not safe to turn off your computer"),
    ('silent strike & em', "it's not safe to turn off your computer"),
    ('silent strike feat. em', "it's not safe to turn off your computer"),
    ('silent strike featuring em', "it's not safe to turn off your computer"),
    ('silent strike, em', "it's not safe to turn off your computer"),

}


def v101_radio_key(artist, title):
    return (" ".join(str(artist).casefold().split()),
            " ".join(str(title).casefold().split()))


def v101_radio_x_studio_title(title):
    """v127: Radio X session suffix is broninformatie, geen gewenste live-versie."""
    value = str(title)
    # Alleen een afsluitende Radio X-vermelding tussen haakjes/haakjesparen.
    return re.sub(
        r"\s*[\(\[]\s*(?=[^\)\]]*\bradio\s*x\b)"
        r"(?:[^\)\]]*)[\)\]]\s*$",
        "", value, flags=re.I,
    ).strip()


def v101_safe_title_spelling(title):
    """Alleen exacte, algemeen bekende orthografische varianten."""
    text = str(title).casefold().strip()
    text = re.sub(r"[?!]+$", "", text).strip()
    text = re.sub(r"\brealise\b", "realize", text)
    return text


# v81: gecontroleerde cataloguslocators bij een Spotify Search-indexprobleem.
# De track-ID is een LOCATOR, geen gegarandeerde match. Via GET /tracks/{id}
# doorloopt de kandidaat dezelfde artiest-, titel-, regio- en versietoetsen.
# Geen vrij toepasbare fuzzy uitzondering en geen tweede Spotify Search.
V81_VERIFIED_CATALOG_TRACKS = {
    # v94: user-confirmed original studio recording; GET /tracks validates it.
    ("the cure", "the snakepit"): "2VeryXhfwHZmwHEYqB0phS",
    ("gipsy kings", "recuerdo apasionado"): "4I1hdRXL4tCnbtJfuqv58A",
    # v87: aparte BE-cataloguscontrole; track-ID is alleen een locator.
    # Elke kandidaat moet nog door de bestaande volledige matcher.
    ("nick drake", "hangin on a star"): "3lpkLZfD2RJltSaAGgmoxb",
    ("nick drake", "hangin' on a star"): "3lpkLZfD2RJltSaAGgmoxb",
    ("nick drake", "hanging on a star"): "3lpkLZfD2RJltSaAGgmoxb",
    ("bon iver", "22 (over s??n)"): "3EYj5rxRbNM3nijF9dOtry",
    ("bon iver", "22 (over s∞∞n)"): "3EYj5rxRbNM3nijF9dOtry",
    ("this is lorelei", "box for buddy, box for star"): "0ktm6PQBeehUHJORIH76UX",
    # v87-batch: publieke Spotify-track plus volledige markt-, artiest- en titelvalidatie.
    ("ludwig van beethoven", "für elise"): "1REPTIRIQ4zI15g6rD2bpX",
    ("nick lowe", "when i write the book"): "5UN8ZYczY8p56eRWhZAKVm",
    # v89: publiek bekende originele opname; uitsluitend GET-kandidaat.
    # Volledige validatie blijft verplicht, geen toelating op basis van dit ID.
    ("pieta brown", "lullaby"): "6TnvLATtSG3WsW9vUuUZgQ",
    # v91: RadioBox voegt Phoebe Bridgers toe aan de hoofdartiestcredit.
    # De officiële Spotify-credit is jasmine.4.t; ID blijft alleen locator
    # en wordt via GET /tracks volledig gevalideerd.
    ("jasmine.4.t & phoebe bridgers", "guy fawkes tesco dissociation"): "6bPvOeqJRytjU4KFl6Wzdy",
    # v88: exact door gebruiker geteste Spotify-links; GET + volledige validatie.
    ("anoushka shankar & karsh kale", "easy (w/ norah jones)"): "1Zlp3AkCc1CCtp3yUwqdRr",
    ("casualties of cool", "flight"): "73qdi1UuN5aHXwG2trXim4",
    ("gabriels", "angels & queens"): "3C0kO7Bc51DEcJMep1deQg",
    ("jordan rakei & jalen ngonda", "what it gave me"): "40QovgBEbr3XnqTJA55jLC",
    ("manassas", "colorado"): "6VyuVYEJnZmlEQ5GT9LQvT",
}


def v81_catalog_locator(artist, title):
    key = (" ".join(str(artist).casefold().split()),
           " ".join(str(title).casefold().split()))
    return (V101_VERIFIED_CATALOG_TRACKS.get(key)
            or V81_VERIFIED_CATALOG_TRACKS.get(key))


# === v82: veilige cataloguskennis en uitlegbare zoekstrategie ===
# Uitsluitend identieke RadioBox artiest/titel sleutels. Een onthouden URI
# is een locator, NOOIT toestemming om de kandidaat zonder validatie te kiezen.
def v82_confirmed_locator(cache, artist, title):
    records = cache.get('__v82_confirmed_catalog', {})
    if not isinstance(records, dict):
        return None
    record = records.get(_v47_key(artist, title))
    if not isinstance(record, dict):
        return None
    uri = record.get('uri', '')
    if isinstance(uri, str) and re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}', uri):
        return uri.rsplit(':', 1)[1]
    return None


def v82_remember_catalog(cache, artist, title, uri, metadata):
    if not metadata or not isinstance(metadata, (tuple, list)) or len(metadata) != 2:
        return False
    if not isinstance(uri, str) or not re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}', uri):
        return False
    records = cache.setdefault('__v82_confirmed_catalog', {})
    if not isinstance(records, dict):
        return False
    key = _v47_key(artist, title)
    if key not in records and len(records) >= 2000:
        return False
    records[key] = {'uri': uri, 'artist': str(metadata[0])[:160],
                    'title': str(metadata[1])[:320]}
    return True


def v82_match_diagnosis(items, artist, title):
    # Dit is uitsluitend uitleg bij een afwijzing, geen acceptatiebeslissing.
    if not items:
        return 'geen_resultaten'
    playable = [x for x in items if isinstance(x, dict)
                and x.get('is_playable') is not False]
    if not playable:
        return 'niet_afspeelbaar'
    def clean(text):
        import unicodedata
        text = unicodedata.normalize('NFKD', v80_unicode_search_text(text).casefold())
        return ''.join(ch for ch in text if ch.isalnum() and not unicodedata.combining(ch))
    wanted_artist, wanted_title = clean(artist), clean(title)
    artist_hits = [x for x in playable if wanted_artist in
                   [clean(a.get('name', '')) for a in x.get('artists', []) if isinstance(a, dict)]]
    if not artist_hits:
        return 'artiestcredits_of_rangschikking'
    if not any(clean(x.get('name', '')) == wanted_title for x in artist_hits):
        return 'titel_of_versie_verschilt'
    return 'veiligheidscontrole_of_ambiguiteit'


def find_spotify_track(
    artist,
    title,
    search_variant=0
):
    global LAST_SPOTIFY_MATCH_ISRC, LAST_SPOTIFY_MATCH_METADATA
    LAST_SPOTIFY_MATCH_ISRC = None
    LAST_SPOTIFY_MATCH_METADATA = None

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

    v101_original_key = v101_radio_key(artist, title)
    if v101_original_key in V101_EXCLUDED_RADIO_TRACKS:
        print(f"⏭️ v101: gebruiker heeft deze opname uitgesloten: {artist} — {title}")
        return None
    # Alleen expliciete Radio X-sessietag mag als gewone studio-opname gelden.
    # Alle andere live/akoestische/remix-specificaties blijven streng.
    if v101_radio_x_studio_title(title) != str(title).strip():
        title = v101_radio_x_studio_title(title)
        print(f"📝 v101: Radio X-sessietag genegeerd; studio-opname: {artist} — {title}")

    # v87 batch-15: alleen deze exacte RadioBox-credit, bevestigd door gebruiker.
    # War nam "Summer" op; dit is geen algemene Eric Burdon/War-alias.
    if (" ".join(str(artist).casefold().split()),
        " ".join(str(title).casefold().split())) == ("eric burdon & war", "summer"):
        artist = "War"
        print("📝 Bevestigde cataloguscredit: Eric Burdon & War — Summer → War — Summer")

    # v88: uitsluitend exacte, door gebruiker gecontroleerde radiocredits.
    # Cataloguslocators worden nog steeds gevalideerd; nooit vrij aliasen.
    v88_radio_key = (" ".join(str(artist).casefold().split()),
                     " ".join(str(title).casefold().split()))
    if v88_radio_key == ("casualties of cool", "flight"):
        artist = "Devin Townsend & Ché Aimee Dorval"
        print("📝 v88: Casualties of Cool — Flight → Devin Townsend & Ché Aimee Dorval")
    elif v88_radio_key == ("manassas", "colorado"):
        artist = "Stephen Stills"
        print("📝 v88: Manassas — Colorado → Stephen Stills (albumcontrole verplicht)")
    elif v88_radio_key == ("jasmine.4.t & phoebe bridgers", "guy fawkes tesco dissociation"):
        artist = "jasmine.4.t"
        print("📝 v91: RadioBox-duetcredit → Spotify-hoofdartiest jasmine.4.t")
    elif v88_radio_key == ("波卡利甜 pocari sweet", "by the ocean"):
        # Exacte RadioBox-credit en titel; geen algemene versoepeling.
        # Spotify zet de Latijnse naam vóór de Chinese naam, aaneengeschreven.
        artist = "Pocari Sweet波卡利甜"
        print("📝 Exacte artiestcorrectie: 波卡利甜 Pocari Sweet → Pocari Sweet波卡利甜")

    # v127: gerichte, bevestigde schrijfwijzen (geen fuzzy zoekopdrachten).
    v127_artist_key = " ".join(str(artist).casefold().split())
    if v127_artist_key == "llyod cole":
        artist = "Lloyd Cole"
    elif v127_artist_key == "llyod cole & the commotions":
        artist = "Lloyd Cole & The Commotions"
    elif v127_artist_key in {"/- {plus/minus}", "/- (plus/minus)", "+/- {plus/minus}", "plus/minus"}:
        artist = "+/-"
    v127_key = (" ".join(str(artist).casefold().split()),
                " ".join(str(title).casefold().split()))
    if v127_key == ("phoenix", "liztomania"):
        title = "Lisztomania"
    elif v127_key == ("white lies", "getting even (demo)"):
        title = "Getting Even"   # gewone opname/remaster, exact dezelfde song
    known_artist = " ".join(
        artist.strip().casefold()
        .replace("feat.", "feat")
        .split()
    )

    known_title = " ".join(
        title.strip().casefold().split()
    )

    # v76: uitsluitend deze door de gebruiker bevestigde RadioBox-titel.
    # Corrigeer de ZOEKtitel vóór Spotify Search, maar behoud alle bestaande
    # Spotify-controles op artiest, afspeelbaarheid en versie.
    if (known_artist, known_title) == (
        "jackson browne", "sing my songs for everyman"
    ):
        print("📝 RadioBox-titelcorrectie: Jackson Browne — Sing My Songs to Me")
        title = "Sing My Songs to Me"
        known_title = title.casefold()

    # v77: gecontroleerde RadioBox-catalogustitels. De aanpassing gebeurt
    # voor het zoeken; de gewone artiest-, titel-, regio- en versiechecks
    # blijven vereist. Geen vrije fuzzy vervanging van ontbrekende woorden.
    confirmed_radio_titles = {
        ("don williams", "'till the rivers run dry"): "'Till The Rivers All Run Dry",
        ("don williams", "till the rivers run dry"): "'Till The Rivers All Run Dry",
        ("prince", "affirmations way back home"): "Way Back Home",
    }
    corrected_title = confirmed_radio_titles.get((known_artist, known_title))
    if corrected_title:
        print(f"📝 Bevestigde RadioBox-titelcorrectie: {artist} — {corrected_title}")
        title = corrected_title
        known_title = title.casefold()

    known_uri_overrides = {
        # Verifieerbare originele Spotify-uitvoeringen wanneer Search enkel
        # covers/karaoke laat zien (beperkt tot exacte artiest en titel).
        ("bird york", "in the deep"): "spotify:track:5JiFBL8ty9N5Zyy8hiV0Qg",
        # v49: exacte Spotify-links die de gebruiker bij gemiste matches gaf.
        # Alleen deze precieze artiest/titel-combinaties, geen fuzzy alias.
        ("father john misty", "to r."): "spotify:track:3aSBBiVguFashsLChx8JZN",
        ("iso68", "est plus"): "spotify:track:3IhIPnC66fiNtnNby3VGTm",
        # v39: exacte, door gebruiker aangewezen Spotify-tracks.
        # Albumopname/uitvoerder blijven via deze expliciete sleutel afgebakend.
        ("alison krauss & gillian welch", "i'll fly away"): "spotify:track:4rJtUMlnhJzlzlnxyoc3tb",
        ("béla fleck", "shanti"): "spotify:track:54auLP9WyrASUYMMBJQVdn",
        ("clannad", "harry's game"): "spotify:track:7CTSDg60OC15XUJusBLPuo",
        # v38: door gebruiker met exacte Spotify-link bevestigde versies.
        ("john lennon", "imagine"): "spotify:track:7pKfPomDEeI4TPT6EOYjn9",
        ("gary numan", "down in the park (piano version)"): "spotify:track:34JQZdbVOrShEVhkYCUuNK",
        ("jimin oh-havenith", "prelude in c major (js bach)"): "spotify:track:50jjQJKueYPhNnJmAzMN6O",
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

        # RadioBox geeft alleen artiest + basistitel. Voor deze opname is
        # door handmatige controle bevestigd welke Spotify-opname bedoeld is.
        (
            "sophia",
            "oh my love",
        ): "spotify:track:6Cume4afdQJnWFFpVPRds1",

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

        # === VUURLAND MATCHER v28 STRICT CREDIT FIX ===
        # Door gebruiker gecontroleerde RadioBox -> Spotify-opnames.
        (
            "the beatles",
            "dear prudence",
        ): "spotify:track:5NQYyej46WQkgCbnzGD21W",

        (
            "johann sebastian bach",
            "prelude #1 in c",
        ): "spotify:track:0laoMHZRUJypy5DzuUBIuT",

        (
            "antonio vivaldi",
            "summer - allegro non molto",
        ): "spotify:track:7LzhdKvW75fFqTWBLEgHtb",
        ("antonio vivaldi", "summer – allegro non molto"): "spotify:track:7LzhdKvW75fFqTWBLEgHtb",

        (
            "suzanne vega",
            "tom's diner (2010)",
        ): "spotify:track:4ytYDfE4i1C1IeD8W79gab",

        # v32: door de gebruiker bevestigde opnames; exacte RadioBox-keys.
        # Niet veralgemenen tot willekeurige gastartiesten of titelprefixen.
        ("sam roberts", "hard road"): "spotify:track:3am6WjJ2mEcOsSSTHplTJ3",
        ("liz cooper & the stampede", "the night"): "spotify:track:5I6gBia5fPMCqy3ry4WJ4l",
        ("lyle lovett", "friend of the devil"): "spotify:track:5ZLzl6T8JwqMTMdoE0nCbU",
        ("robert plant", "killing the blues"): "spotify:track:4MiX7j4kYbWZlGOimqFvtE",
        ("kids with buns", "nothing"): "spotify:track:7ncRC6F2HAUuPGquz86dvX",
    }

    known_uri = known_uri_overrides.get(
        (known_artist, known_title)
    )

    if known_uri and v101_original_key not in V101_VERIFIED_CATALOG_TRACKS:
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
    def split_title_feature(value):
        """
        Splits only explicit feature metadata from a title.

        Plain-language title words such as "Handle with Care" must remain
        part of the song title. Therefore bare `with X` is never treated as
        a feature marker; `with` is only accepted inside parentheses.
        """
        raw = str(value or "").strip()

        explicit = re.search(
            r"(?:\s+|\s*\()\s*(?:feat\.?|ft\.?|featuring|w/)\s+"
            r"([^\(\)\[\]]+?)\)?\s*$",
            raw,
            flags=re.IGNORECASE,
        )
        if explicit:
            return raw[:explicit.start()].strip(), explicit.group(1).strip()

        parenthesized_with = re.search(
            r"\s*\(\s*with\s+([^()\[\]]+?)\s*\)\s*$",
            raw,
            flags=re.IGNORECASE,
        )
        if parenthesized_with:
            return (
                raw[:parenthesized_with.start()].strip(),
                parenthesized_with.group(1).strip(),
            )

        return raw, None

    search_title, title_feature_artist = split_title_feature(title)

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
        # Spotify kan een officiële bandcredit als "&" of "and" tonen.
        # Beide kanten van de gecontroleerde alias worden identiek behandeld.
        value = re.sub(r"\s*&\s*", " and ", value)
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return " ".join(value.split())

    # Radioproject met bandleden tussen haakjes: Spotify gebruikt de
    # projectnaam als hoofdartiest en de leden als extra artiestobjects.
    project_credit = re.match(r'^(.+?)\s*\(([^()]+)\)\s*$', primary_search_artist)
    if project_credit and len(v71_credit_parts(project_credit.group(2))) >= 2:
        primary_search_artist = project_credit.group(1).strip()

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
        text = _numbered_title_equivalent(value).replace("’", "'")

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

    # v80: gekozen zoekroute uit schrijfwijzen; geen extra aanvraag.
    # Bewezen catalogushints hebben voorrang, maar zijn nooit vrijstellingen
    # van de originele artiest-, titel- en afspeelbaarheidscontrole.
    learned_spellings = load_cache().get('__v80_confirmed_spellings', {})
    learned_entry = learned_spellings.get(_v47_key(artist, title)) if isinstance(learned_spellings, dict) else None
    route = v80_search_route(primary_search_artist, search_title, search_variant,
                             learned_entry if isinstance(learned_entry, dict) else None)
    if learned_entry and route['reason'] == 'confirmed_catalog_spellings':
        search_title = route['title']
        spotify_search_artist = route['artist']
    else:
        search_title = v80_unicode_search_text(search_title)

    # v77: Spotify catalogiseert sommige enkelwoordtitels als losse
    # letters (Speyside -> S P E Y S I D E). Alleen op een later zoekpad
    # één structureel gespelde zoekterm; geen extra Spotify HTTP-call.
    if (search_variant == 1 and re.fullmatch(r"[A-Za-z]{6,16}", str(search_title).strip())):
        search_title = " ".join(str(search_title).strip().upper())

    # v79: een bekende structureel gespatieerde catalogustitel mag al
    # bij de eerste zoekpoging met de Spotify-schrijfwijze gezocht worden.
    # Dit is uitsluitend een zoekvorm, geen bypass van de veilige matcher.
    if (search_variant == 0 and
        str(primary_search_artist).casefold().strip() == "bon iver" and
        str(search_title).casefold().strip() == "speyside"):
        search_title = "S P E Y S I D E"

    # v38: benoemde versies horen bij zoekpoging nul in de zoekterm te
    # blijven; anders vinden we b.v. een pianoversie vaak niet.
    explicit_version_request = re.search(
        r"\(\s*(piano|acoustic|orchestral|live|remix|instrumental)\s+version\s*\)\s*$",
        str(title or ""), flags=re.IGNORECASE
    )
    if explicit_version_request and search_variant == 0:
        search_title = str(title).strip()
    search_query_title = spotify_search_title_variant(search_title)
    # v51: maak de EERSTE zoekopdracht ook bruikbaar als Spotify het werk
    # anders catalogiseert. De latere varianten behouden het oorspronkelijke
    # zoekpad; geen extra requests of versoepelde kandidaatselectie.
    if search_variant == 0:
        classical_query = re.match(
            r"(?i)^prelude\s+to\s+cello\s+suite\s*(?:#|no\.?\s*)?([1-6])\b",
            str(search_title).strip(),
        )
        if classical_query:
            search_query_title = f"Cello Suite No. {classical_query.group(1)} Prelude"
        else:
            # Descriptieve titelverduidelijking is niet hetzelfde als een
            # uitvoeringsversie: '(Acoustic)' of '(Live)' blijft bewaard.
            descriptive = re.fullmatch(r"(.{7,}?)\s*\(([^()]{4,75})\)",
                                        str(search_title).strip())
            if descriptive and not re.search(
                r"(?i)\b(?:live|acoustic|remix|mix|demo|edit|version|instrumental|session|take)\b",
                descriptive.group(2),
            ):
                search_query_title = spotify_search_title_variant(descriptive.group(1))
            search_query_title = re.sub(
                r"(?i)\b(?:a|one)\s+million\s+dollars?\b",
                "$1,000,000", search_query_title,
            )

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
    #
    # Bij een duidelijke artiestnaam met precies twee betekenisvolle tokens
    # zetten we de artiest vóór de titel. Dat helpt vooral bij veelgebruikte
    # titels (bv. "Holding on to You") en kleine titelspelfouten
    # (bv. "Yemanja" -> "Iemanja"), zonder een harde artist:-filter te
    # gebruiken. Project-/groepnamen met meer tokens blijven titel-eerst,
    # zodat album/project-as-artist rescues niet onnodig worden benadeeld.
    if len(safe_artist_hint_parts) == 2:
        query_parts = (artist_hint, search_query_title)
    else:
        query_parts = (search_query_title, artist_hint)

    query = " ".join(
        part for part in query_parts
        if str(part or "").strip()
    )

    # v98: bij samengestelde artiestcredits met meerdere afzonderlijke
    # namen rangschikt Spotify de volledige radio-string soms slecht.
    # Gebruik enkel de eerste volledige naam plus exacte titel als zoekhint;
    # ALLE artiesten blijven verplicht in de lokale kandidaatvalidatie.
    v98_search_collaborators = re.split(
        r'\s*,\s*|\s+(?:&|and)\s+',
        str(primary_search_artist or ''), flags=re.I
    )
    if len(v98_search_collaborators) >= 2 and all(
        len(x.strip()) >= 4 for x in v98_search_collaborators
    ):
        first_credit = v98_search_collaborators[0].strip()
        if len(first_credit) < 5:
            first_credit = v98_search_collaborators[-1].strip()
        query = f'"{first_credit}" {search_query_title}'

    # Bij titels van losse letters + een lange artiestnaam verhindert het
    # fragment 'School of' vaak de vindbaarheid; zoek de GEHELE artiest.
    if re.fullmatch(r'(?:[A-Za-z]\s+){2,}[A-Za-z]', str(search_query_title).strip()):
        query = f'"{spotify_search_artist}" "{search_query_title}"'

    # Houd een remaster-jaartal uit de zoekquery; de muziekidentiteit
    # en versiekeuze worden NADAT Spotify kandidaten geeft gecontroleerd.
    if re.search(r'(?i)\(\s*\d{4}\s+remaster(?:ed)?\s*\)\s*$', str(search_title)):
        core = re.sub(r'(?i)\s*\(\s*\d{4}\s+remaster(?:ed)?\s*\)\s*$', '', str(search_title)).strip()
        if core:
            query = f'artist:"{spotify_search_artist}" track:"{core}"'

    # v49: ultrakorte titels zijn moeilijk te ranken met een ingekorte
    # artiestennaam (bv. "To R. Father John"). Gebruik meteen de volledige
    # artiest + exact afgebakende titel. Bij latere varianten blijft het
    # bestaande alternatieve zoekpad beschikbaar.
    if search_variant == 0 and len(search_title_words) <= 2 and len(search_query_title.strip()) <= 12:
        quoted_artist = str(spotify_search_artist).replace('"', ' ').strip()
        quoted_title = search_query_title.replace('"', ' ').strip()
        if quoted_artist and quoted_title:
            query = f'artist:"{quoted_artist}" track:"{quoted_title}"'

    # v98: ultrakorte titels met samengestelde artiestcredits hoeven niet
    # de letterlijk samengevoegde RadioBox-string als artist:-veld te hebben.
    if len(v98_search_collaborators) >= 2 and all(
        len(x.strip()) >= 4 for x in v98_search_collaborators
    ) and search_variant == 0:
        first_credit = v98_search_collaborators[0].strip()
        if len(first_credit) < 5:
            first_credit = v98_search_collaborators[-1].strip()
        query = f'"{first_credit}" {search_query_title}'

    # v98: niet onnodig filteren op een algemene EP-versieaanduiding.
    # De eindmatch controleert wel de EP-familie.
    if (search_variant == 0 and
            re.search(r'(?i)\(\s*ep\s+version\s*\)\s*$', str(search_title))):
        core = re.sub(r'(?i)\s*\(\s*ep\s+version\s*\)\s*$', '', str(search_title)).strip()
        if core:
            query = f'"{spotify_search_artist}" "{core}"'

    # v52.1: Zoekstrategie 1/2 gebruikt de KERNTITEL als de bron een
    # uitvoeringslabel toevoegt. Versievoorkeur blijft uitsluitend in de
    # kandidaatselectie; zoekresultaten mogen niet door '(live)' verdwijnen.
    # Bij langere titels filteren we enkele functiewoorden uit de tweede
    # zoekopdracht, zodat een kleine bronfout ('Was' vs 'Has') niet opnieuw
    # exact dezelfde Spotify-ranking veroorzaakt.
    def v521_broad_catalog_title(value):
        text = str(value or '').strip()
        text = re.sub(
            r'\s*\(\s*(?:(?:live|remastered?|remaster|acoustic|studio|demo|instrumental|radio edit|single edit|club mix|extended mix|remix)(?:\s+(?:version|recording|mix|edit))?|(?:\d{4}\s+)?remaster)\s*\)\s*$',
            '', text, flags=re.IGNORECASE,
        ).strip()
        # Ook het veel voorkomende ' - Live' en ' - 2019 Remaster'.
        text = re.sub(
            r'\s+[-–—]\s+(?:(?:live|acoustic|demo|instrumental)(?:\s+version)?|(?:\d{4}\s+)?remaster(?:ed)?|(?:club|radio|extended)\s+mix)\s*$',
            '', text, flags=re.IGNORECASE,
        ).strip()
        return text or str(value or '').strip()

    def v521_distinct_search_terms(value):
        words = re.findall(r"[\w'’]+", value, flags=re.UNICODE)
        if len(words) >= 5:
            stop = {'the', 'a', 'an', 'of', 'and', 'or', 'was', 'has',
                    'is', 'are', 'were', 'been', 'to', 'in', 'on', 'at'}
            pruned = [word for word in words if word.casefold() not in stop]
            if len(pruned) >= 2:
                return ' '.join(pruned[:6])
        return value

    # v34: alternatieve query PAS bij de volgende sync-ronde.
    # Ook deze zoekpoging vraagt maximaal tien Spotify-resultaten.
    # Geen extra Spotify API-call in find_spotify_track().
    if search_variant == 1 and title_feature_artist:
        # v51.8: RadioBox kan de hoofdartiest en gast verwisselen.
        # Eén ALTERNATIEVE bestaande zoekpoging op de expliciet genoemde
        # gast, niet een extra Spotify-request. De uiteindelijke match
        # blijft beperkt tot een EXACTE gastcredit en exacte kerntitel.
        guest_query = " ".join(str(title_feature_artist).replace('"', ' ').split())
        query = " ".join(part for part in (guest_query, search_query_title) if part)
    elif search_variant == 1:
        # Exacte titel als gerichte track-filter; de artiest controleren
        # we achteraf in de bestaande strenge matcher.
        quoted_title = search_query_title.replace('"', ' ').strip()
        short_title = len(re.findall(r"[\w]+", quoted_title)) <= 2
        if short_title:
            # v51.7: poging 0 gebruikte bij ultrakorte titels al
            # artist:"..." track:"...". Dezelfde velden omdraaien
            # verandert de Spotify-filter niet en verspilt een poging.
            # Daarom is poging 1 nu een ongefilterde catalogusquery:
            # Spotify mag alternatieve credits en titelspelling ranken;
            # onze strenge lokale matcher valideert elke kandidaat.
            loose_artist = str(spotify_search_artist).replace('"', ' ').strip()
            loose_artist = loose_artist.translate(str.maketrans({
                'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'Ae',
                'œ': 'oe', 'Œ': 'Oe', 'ß': 'ss',
            }))
            # v72: niet op één artist:-veld vastlopen wanneer Spotify
            # een samenwerking als twee artist-objects opslaat.
            # Volledige artiestnaam blijft een zachte zoekhint; de
            # uiteindelijke kandidaat krijgt een strenge creditcontrole.
            # v79: een track:-filter met losse letters kan de juiste opname
            # wegfilteren. Maak bij deze STRUCTURELE schrijfwijze een vrije
            # catalogusquery (de kandidaatvalidatie blijft strikt).
            is_spaced_letter_title = bool(re.fullmatch(
                r"[A-Za-z](?: [A-Za-z]){5,15}", quoted_title
            ))
            if is_spaced_letter_title:
                query = ' '.join(part for part in (loose_artist, f'"{quoted_title}"') if part)
            else:
                query = ' '.join(part for part in (f'track:"{quoted_title}"', loose_artist) if part)
        else:
            # Zoek met de artiest als ZACHTE hint en een brede kerntitel.
            # Een harde track:-filter op bronmetadata, bv. '(live)', sloot
            # echte Spotify-kandidaten onnodig uit.
            core_title = v521_broad_catalog_title(search_query_title)
            broad_title = v521_distinct_search_terms(core_title)
            loose_artist = str(spotify_search_artist).replace('"', ' ').strip()
            query = ' '.join(part for part in (loose_artist, broad_title) if part)
    elif search_variant == 2:
        # Gerichte artiestfilter, maar zonder verplichte versie-achtervoegsels
        # of mogelijk foutieve kleine functiewoorden in de bronmetadata.
        quoted_artist = str(spotify_search_artist).replace('"', ' ').strip()
        core_title = v521_broad_catalog_title(search_query_title)
        broad_title = v521_distinct_search_terms(core_title)
        query = f'artist:"{quoted_artist}" {broad_title}'

    # v79: do not prune spaced letters to six tokens.
    if search_variant == 1 and re.fullmatch(r"[A-Za-z](?: [A-Za-z]){5,15}", str(search_query_title)):
        query = f'{spotify_search_artist} "{search_query_title}"'

    # v81: exact geverifieerde cataloguslocator in plaats van nog een
    # vruchteloze Search. Maximaal één Spotify-opzoekactie per ronde;
    # de gemeenschappelijke kandidaatvalidatie hieronder blijft intact.
    catalog_id = v81_catalog_locator(*v101_original_key) or (v81_catalog_locator(*v88_radio_key) if v88_radio_key in {("casualties of cool", "flight"), ("manassas", "colorado"), ("jasmine.4.t & phoebe bridgers", "guy fawkes tesco dissociation")} else v81_catalog_locator(artist, title))
    catalog_reason = 'v81' if catalog_id else None
    if not catalog_id:
        catalog_id = v82_confirmed_locator(load_cache(), artist, title)
        if catalog_id:
            catalog_reason = 'v82'
    if catalog_id:
        print(f"📀 {catalog_reason} cataloguscontrole: {artist} — {title} (geen Search nodig; volledige validatie)")
        catalog_track = spotify_request(
            "GET", f"/tracks/{catalog_id}", params={"market": "from_token"}
        )
        data = {"tracks": {"items": [catalog_track] if isinstance(catalog_track, dict)
                                           and catalog_track.get("id") == catalog_id else []}}
    else:
        data = spotify_request(
            "GET",
            "/search",
            params={
            "q": query,
            "type": "track",
            "limit": 10,
            # Spotify bepaalt de afspeelbaarheid voor het land van de
            # ingelogde gebruiker. Geen hardcoded BE of extra HTTP-call.
            "market": "from_token",
            }
        )

    items = data.get(
        "tracks",
        {}
    ).get(
        "items",
        []
    )

    # ---------------------------------------------------------
    # ALGEMENE STRUCTURELE SEARCH-RESCUE
    # ---------------------------------------------------------
    # De eerste Spotify Search blijft breed en goedkoop. Alleen wanneer de
    # top-10 geen kandidaat bevat die zowel qua artiest als qua titelvorm
    # plausibel is, doen we maximaal EEN extra gerichte Search.
    #
    # Die rescue is bedoeld voor catalogus-vormverschillen, niet voor fuzzy
    # gokken. Voorbeelden:
    #   Speyside <-> S P E Y S I D E
    #   Yemanja  <-> Iemanja
    #   veelgebruikte titel + juiste artiest (Holding on to You)
    #
    # De uiteindelijke kandidaatselectie hieronder blijft onaangeraakt en
    # controleert nog steeds streng artiest, kerntitel, versie en ambiguiteit.
    def search_identity(value):
        raw = str(value or "").casefold().replace("’", "'")
        raw = unicodedata.normalize("NFKD", raw)
        raw = "".join(
            char for char in raw
            if not unicodedata.combining(char)
        )
        return "".join(char for char in raw if char.isalnum())

    def search_words(value):
        raw = str(value or "").casefold().replace("’", "'")
        raw = unicodedata.normalize("NFKD", raw)
        raw = "".join(
            char for char in raw
            if not unicodedata.combining(char)
        )
        raw = re.sub(r"[^a-z0-9']+", " ", raw)
        return [part for part in raw.split() if part]

    def search_title_structural_equivalent(left, right):
        left_id = search_identity(left)
        right_id = search_identity(right)
        if left_id and left_id == right_id:
            return True

        left_words = search_words(left)
        right_words = search_words(right)
        if left_words == right_words and left_words:
            return True

        # Eén optioneel "the" mag ontbreken.
        if abs(len(left_words) - len(right_words)) == 1:
            longer, shorter = (
                (left_words, right_words)
                if len(left_words) > len(right_words)
                else (right_words, left_words)
            )
            for i, token in enumerate(longer):
                if token == "the" and longer[:i] + longer[i + 1:] == shorter:
                    return True

        # Veilige AKA-catalogustitel: één kant mag exact één van de
        # twee volledige titeldelen zijn. Geen losse substring-match.
        for full_words, short_words in ((left_words, right_words), (right_words, left_words)):
            if "aka" in full_words and short_words:
                aka_index = full_words.index("aka")
                before = full_words[:aka_index]
                after = full_words[aka_index + 1:]
                if short_words == before or short_words == after:
                    return True

        # Eén veilig voorzetsel vooraan, bv. My Secret Life / In My Secret Life.
        if abs(len(left_words) - len(right_words)) == 1:
            longer, shorter = (
                (left_words, right_words)
                if len(left_words) > len(right_words)
                else (right_words, left_words)
            )
            if (
                len(shorter) >= 3
                and longer[0] in {"in", "on", "at", "from", "to"}
                and longer[1:] == shorter
            ):
                return True

        # Zeer smalle Y/I/J-transliteratie aan het begin van één lang woord.
        if (
            len(left_words) == 1
            and len(right_words) == 1
            and len(left_id) >= 6
            and len(left_id) == len(right_id)
            and left_id[1:] == right_id[1:]
            and left_id[:1] != right_id[:1]
            and {left_id[:1], right_id[:1]} <= {"y", "i", "j"}
        ):
            return True

        return False

    def search_artist_plausible(item):
        candidate_names = [
            str(obj.get("name", ""))
            for obj in item.get("artists", [])
            if obj.get("name")
        ]
        if not candidate_names:
            return False

        wanted_names = {
            str(primary_search_artist or ""),
            str(spotify_search_artist or ""),
        }
        wanted_names.update(str(alias) for alias in search_artist_aliases)

        wanted_ids = {search_identity(name) for name in wanted_names if name}
        candidate_ids = {search_identity(name) for name in candidate_names if name}

        # Ook de gecombineerde officiële Spotify-artist objects meenemen.
        if len(candidate_names) > 1:
            candidate_ids.add(search_identity(" and ".join(candidate_names)))

        # Metadata van sommige Spotify-artiesten schrijft een solist uit
        # als '[solist] and/with [band]'. Dit geeft uitsluitend toestemming
        # om de kandidaat inhoudelijk te beoordelen; de titel-/versiecontrole
        # hieronder blijft beslissend.
        if any(
            candidate.startswith(wanted + connector)
            and len(candidate) > len(wanted + connector) + 2
            for wanted in wanted_ids if len(wanted.split()) >= 2
            for candidate in candidate_ids
            for connector in (' and ', ' with ')
        ):
            return True

        for wanted_id in wanted_ids:
            if not wanted_id:
                continue
            for candidate_id in candidate_ids:
                if not candidate_id:
                    continue
                if wanted_id == candidate_id:
                    return True
                # Alleen om te beslissen OF een rescue nodig is; dit accepteert
                # zelf nooit een track. Houd deze drempel bewust zeer hoog:
                # een middelmatige artiestgelijkenis mag de gerichte rescue
                # niet blokkeren.
                if SequenceMatcher(None, wanted_id, candidate_id).ratio() >= 0.985:
                    return True
        return False

    def search_version_hint(value):
        """Versieclassificatie voor rescue-gating; bekijk alle suffixsegmenten."""
        raw = str(value or "").casefold().replace("–", "-").replace("—", "-")
        segments = re.findall(r"\(([^()]*)\)", raw)
        dash_parts = re.split(r"\s+-\s+", raw)
        if len(dash_parts) > 1:
            segments.extend(dash_parts[1:])
        suffix = " | ".join(part.strip() for part in segments if part.strip())
        if not suffix:
            return None
        checks = (
            ("live", r"\blive\b"),
            ("acoustic", r"\bacoustic\b"),
            ("remix", r"\bremix\b"),
            ("mix", r"\bmix\b"),
            ("demo", r"\bdemo\b"),
            ("instrumental", r"\binstrumental\b"),
            ("arrangement", r"\b(?:arr\.?|arranged)\s+(?:for|by)\b"),
            ("edit", r"\b(?:radio\s+)?edit\b"),
            ("alternate", r"\b(?:alternate|alternative)\b"),
            ("unplugged", r"\bunplugged\b"),
            ("stripped", r"\bstripped\b"),
            ("session", r"\bsession\b"),
            ("remaster", r"\bremaster(?:ed)?\b"),
            ("named version", r"\b\w[\w -]*\s+version\b"),
        )
        for family, pattern in checks:
            if re.search(pattern, suffix):
                return family
        return None

    wanted_search_version = search_version_hint(title)
    hard_search_alternatives = {
        "live", "acoustic", "remix", "mix", "demo", "instrumental",
        "alternate", "unplugged", "stripped", "session", "arrangement",
        "named version",
    }

    def first_search_candidate_blocks_rescue(item):
        if not search_artist_plausible(item):
            return False
        if not search_title_structural_equivalent(search_title, item.get("name", "")):
            return False

        candidate_version = search_version_hint(item.get("name", ""))
        if wanted_search_version:
            # Expliciet gevraagde versie: alleen dezelfde familie is een echte
            # reden om de rescue over te slaan.
            return candidate_version == wanted_search_version

        # Gewone RadioBox-titel: live/remix/etc. mag nooit verhinderen dat we
        # nog naar een gewone/remaster-opname zoeken.
        if candidate_version in hard_search_alternatives:
            return False
        return True

    first_search_has_plausible_match = any(
        first_search_candidate_blocks_rescue(item)
        for item in items
    )

    if False and not first_search_has_plausible_match:  # One Spotify Search per call, hard limit
        title_words_for_rescue = search_words(search_query_title)
        title_id_for_rescue = search_identity(search_query_title)
        rescue_title = search_query_title
        rescue_reason = "focused artist+track"

        # Lange enkelwoordtitels krijgen een structurele catalogusvariant.
        if (
            len(title_words_for_rescue) == 1
            and 6 <= len(title_id_for_rescue) <= 24
        ):
            first = title_id_for_rescue[:1]
            transliteration_map = {"y": "i", "j": "i", "i": "y"}
            if first in transliteration_map:
                rescue_title = (
                    transliteration_map[first]
                    + title_id_for_rescue[1:]
                )
                rescue_reason = "initial transliteration"
            else:
                rescue_title = " ".join(title_id_for_rescue.upper())
                rescue_reason = "spaced-letter title"

        # Spotify ondersteunt artist: en track: als officiële Search-filters.
        # We gebruiken die alleen als tweede kans; de eerste brede Search
        # blijft nodig voor aliases, projectcredits en afwijkende metadata.
        rescue_artist = str(spotify_search_artist or primary_search_artist or "").strip()

        # Meerwoordige field-values quoten zodat Spotify de volledige titel
        # en artiest als één zoekwaarde behandelt.
        def spotify_search_quote(value):
            value = str(value or "").replace('"', ' ').strip()
            return f'"{value}"' if value else ""

        rescue_query = " ".join(
            part for part in (
                f"track:{spotify_search_quote(rescue_title)}" if rescue_title else "",
                f"artist:{spotify_search_quote(rescue_artist)}" if rescue_artist else "",
            )
            if part
        )

        if rescue_query and rescue_query != query:
            rescue_data = spotify_request(
                "GET",
                "/search",
                params={
                    "q": rescue_query,
                    "type": "track",
                    "limit": 10,
                    "market": "from_token",
                }
            )

            rescue_items = rescue_data.get(
                "tracks",
                {}
            ).get(
                "items",
                []
            )

            seen_item_ids = {
                item.get("id")
                for item in items
                if item.get("id")
            }
            for rescue_item in rescue_items:
                rescue_id = rescue_item.get("id")
                if rescue_id and rescue_id in seen_item_ids:
                    continue
                items.append(rescue_item)
                if rescue_id:
                    seen_item_ids.add(rescue_id)

            print(
                "🧪 Spotify structurele rescue-query "
                f"({rescue_reason}): {rescue_query}"
            )

    def normalize(value):
        value = str(value or "").lower().strip()

        # NFKD zet ø, ł en ß niet om naar hun gebruikelijke ASCII-vorm.
        # Vóór accentverwijdering veilig translitereren voor metadata-matches.
        value = value.translate(str.maketrans({
            "ø": "o", "ł": "l", "đ": "d", "ð": "d",
            "þ": "th", "æ": "ae", "œ": "oe", "ß": "ss",
        }))

        value = unicodedata.normalize(
            "NFKD",
            value
        )

        value = "".join(
            char
            for char in value
            if not unicodedata.combining(char)
        )

        value = value.replace("’", "'").replace("ʻ", "'").replace("ʼ", "'")
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
        # v87: S∞∞N is gestileerd als SOON; niet twee keer 'oo'.
        # Uitsluitend deze woordvorm, geen algemene fuzzy-versoepeling.
        value = re.sub(r"\bs∞∞n\b", "soon", value)
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

        # v51: uitspraak/valutaspelling. De volledige hoeveelheidswaarde moet
        # identiek zijn; dit is geen vrije fuzzy titelovereenkomst.
        normalized = re.sub(r"\b(?:a|one)\s+million\s+dollars?\b", "1000000", normalized)
        normalized = re.sub(r"\$\s*1\s+000\s+000\b", "1000000", normalized)

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

    def aka_title_equivalent(left, right):
        """Veilige catalogusvariant: "A aka B" <-> exact A of exact B."""
        left_norm = normalize(left).strip()
        right_norm = normalize(right).strip()

        def split_aka(value):
            parts = re.split(r"\s+aka\s+", value, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) != 2:
                return None
            first, second = (part.strip() for part in parts)
            return (first, second) if first and second else None

        for full, short in ((left_norm, right_norm), (right_norm, left_norm)):
            aka_parts = split_aka(full)
            if not aka_parts:
                continue
            short_id = title_identity(short)
            if short_id and short_id in {title_identity(aka_parts[0]), title_identity(aka_parts[1])}:
                return True
        return False


    def leading_preposition_equivalent(left, right):
        """
        Zeer beperkte rescue voor één ontbrekend kort voorzetsel vooraan.

        Voorbeeld: "My Secret Life" <-> "In My Secret Life".
        Alleen geldig als:
        - één titel exact één extra eerste woord heeft;
        - dat woord een kort voorzetsel is;
        - de resterende woorden exact gelijk zijn;
        - de kortere titel minstens 3 woorden bevat.

        De caller vereist daarnaast een exacte primaire artiestmatch.
        """
        left_tokens = title_tokens_without_optional_the(left)
        right_tokens = title_tokens_without_optional_the(right)

        if len(left_tokens) == len(right_tokens):
            return False

        longer, shorter = (
            (left_tokens, right_tokens)
            if len(left_tokens) > len(right_tokens)
            else (right_tokens, left_tokens)
        )

        if len(shorter) < 3 or len(longer) != len(shorter) + 1:
            return False

        safe_prefixes = {"in", "on", "at", "from", "to"}
        return longer[0] in safe_prefixes and longer[1:] == shorter

    def initial_transliteration_equivalent(left, right):
        """
        Zeer smalle transliteratie-rescue voor lange éénwoordtitels.

        Sommige catalogi wisselen een beginnende Y/I/J terwijl de rest van
        de naam exact gelijk blijft, bv. Yemanja <-> Iemanja. We staan dit
        alleen toe als:
        - beide titels uit precies één woord bestaan;
        - het woord minstens 6 letters lang is;
        - alleen de eerste letter verschilt;
        - beide beginletters uit de transliteratieset Y/I/J komen.

        De normale artiestcontrole blijft volledig actief.
        """
        left_value = title_identity(left)
        right_value = title_identity(right)

        if not left_value or not right_value:
            return False
        if " " in normalize(left).strip() or " " in normalize(right).strip():
            return False
        if len(left_value) < 6 or len(left_value) != len(right_value):
            return False
        if left_value[1:] != right_value[1:]:
            return False
        if left_value[0] == right_value[0]:
            return False

        return {left_value[0], right_value[0]} <= {"y", "i", "j"}

    def version_family(value):
        """Classificeer duidelijke versie-segmenten met semantische prioriteit."""
        raw = str(value or "").strip().lower()
        raw = raw.replace("–", "-").replace("—", "-")
        raw = raw.replace("’", "'")  # typografische apostrof in versienaam

        # Een Spotify-titel kan meerdere versie-segmenten combineren, bv.
        # "Treetop Flyer (Live) - Remastered". Bekijk daarom ALLE duidelijke
        # haakjes- en dashsegmenten, niet alleen het allerlaatste suffix.
        suffixes = re.findall(r"\(([^()]*)\)", raw)
        dash_parts = re.split(r"\s+-\s+", raw)
        if len(dash_parts) > 1:
            suffixes.extend(dash_parts[1:])

        context = " | ".join(part.strip() for part in suffixes if part.strip())
        if not context:
            return None

        # Meest betekenisvolle opnamefamilie eerst. Een live-remaster blijft
        # dus live; remaster beschrijft alleen de mastering, niet de uitvoering.
        if re.search(r"\blive\b", context): return "live"
        if re.search(r"\bacoustic\b", context): return "acoustic"
        if re.search(r"\bremix\b", context): return "remix"
        if re.search(r"\bmix\b", context): return "mix"
        if re.search(r"\bdemo\b", context): return "demo"
        if re.search(r"\binstrumental\b", context): return "instrumental"
        if re.search(r"\breprise\b", context): return "reprise"
        if re.search(r"\balternate|alternative\b", context): return "alternate"
        if re.search(r"\bspotify\s+singles?\b", context): return "spotify singles"
        if re.search(r"\bunplugged\b", context): return "unplugged"
        if re.search(r"\bstripped\b", context): return "stripped"
        if re.search(r"\bsession\b", context): return "session"
        if re.search(r"\b(?:alternate\s+)?take\s*\d*\b", context): return "take"
        if re.search(r"\bmono\b", context): return "mono"
        if re.search(r"\bstereo\b", context): return "stereo"
        if re.search(r"\bextended\b", context): return "extended"
        if re.search(r"\bpiano\s+version\b", context): return "piano version"
        if re.search(r"\borchestral\s+version\b", context): return "orchestral version"
        if re.search(r"\b(?:arr\.?|arranged|arrangement)\s+(?:for|by)\b", context): return "arrangement"
        if re.search(r"\b(?:re[- ]?record(?:ed|ing)?|taylor'?s\s+version)\b", context): return "re-recorded"
        if re.search(r"\bsped\s*up\b", context): return "sped up"
        if re.search(r"\bslowed(?:\s*\+?\s*reverb)?\b", context): return "slowed"
        if re.search(r"\bnightcore\b", context): return "nightcore"
        if re.search(r"\bkaraoke\b", context): return "karaoke"
        if re.search(r"\b(?:ep\s+version|ep\s+edit)\b", context): return "ep version"
        if re.search(r"\bradio\s+edit\b", context): return "edit"
        if re.search(r"\bedit\b", context): return "edit"
        if re.search(r"\bbonus\s+track\b", context): return "bonus track"
        if re.search(r"\b(?:radio|single|album)\s+mix\b", context): return "mix"
        if re.search(r"\bsingle\s+version\b", context): return "single version"
        if re.search(r"\balbum\s+version\b", context): return "album version"
        if re.search(r"\boriginal\s+version\b", context): return "original version"
        if re.search(r"\bremaster(?:ed)?\b", context): return "remaster"
        if re.search(r"\b(?:deluxe|anniversary|original|standard)\s+(?:edition|version)\b", context): return "edition"
        if re.search(r"\bversion\b", context):
            # Alleen exact "Version" is neutraal. Benoemde varianten zoals
            # "Mfp Version" / "Then Again Version" blijven apart en lager.
            version_parts = [part for part in suffixes if re.search(r"\bversion\b", part)]
            if any(re.fullmatch(r"\s*version\s*", part) for part in version_parts):
                return "version"
            return "named version"
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
                |(?:arr\.?|arranged)\s+(?:for|by)\s+[^)]*
                |(?:arr\.?|arranged)\s+(?:for|by)\s+.*
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


    def spotify_candidate_version(item):
        """Versiefamilie uit tracktitel, met zeer veilige album-context fallback."""
        track_family = requested_version(item.get("name", ""))
        if track_family:
            return track_family

        album_raw = str((item.get("album") or {}).get("name", "") or "").strip().casefold()
        if not album_raw:
            return None

        # Albumcontext alleen gebruiken bij ondubbelzinnige cataloguslabels.
        # Een album als "Live Through This" is dus GEEN live-signaal.
        album_checks = (
            ("live", r"^(?:live\s*$|live\s+(?:at|from|in|on)\b|.*\blive\s+(?:at|from|in|on)\b)"),
            ("acoustic", r"\bacoustic\s+(?:sessions?|versions?)\b"),
            ("remix", r"\b(?:the\s+)?remixes\b|\bremix\s+(?:album|collection)\b"),
            ("demo", r"\b(?:demos?|demo\s+sessions?)\b"),
            ("instrumental", r"\binstrumental\s+(?:versions?|album)\b"),
            ("karaoke", r"\bkaraoke\s+(?:versions?|album)\b"),
            ("unplugged", r"\bunplugged\b"),
            ("stripped", r"\bstripped\s+(?:sessions?|versions?)\b"),
        )
        for family, pattern in album_checks:
            if re.search(pattern, album_raw, flags=re.IGNORECASE):
                return family
        return None


    def title_base(value):
        """
        Verwijder bekende versie-/credit-aanduidingen van een titel.

        RadioBox en Spotify plaatsen featuring-credits, catalogusversies
        en "From The Vault" niet altijd in hetzelfde veld.
        """
        raw_value = str(value or "").strip()

        # Verklarende prefix:
        # "(Looking For) The Heart Of Saturday Night"
        # -> "The Heart Of Saturday Night".
        leading_context = re.match(
            r"^\(([^()]{1,40})\)\s+(.+)$",
            raw_value
        )
        if leading_context:
            context = leading_context.group(1)
            if not re.search(
                r"\b(?:live|remix|mix|acoustic|demo|edit|version|remaster)\b",
                context,
                flags=re.IGNORECASE
            ):
                raw_value = leading_context.group(2).strip()

        # Benoemde Spotify "Cut" is een catalogussuffix; de naam van de
        # variant wordt hierboven apart streng gecontroleerd.
        raw_value = re.sub(
            r"\s+-\s+[^-()]+?\s+cut\s*$",
            "",
            raw_value,
            flags=re.IGNORECASE
        ).strip()

        # Duidelijke RadioBox credit-/contexthaakjes horen niet bij de titel.
        raw_value = re.sub(
            r"\s*\((?=[^)]*(?:=|\b(?:vocals?|guitar|bass|drums?|piano|keys?|harmony|theme|theme song|soundtrack)\b))[^)]*\)\s*$",
            "",
            raw_value,
            flags=re.IGNORECASE
        ).strip()

        # v71: '(with Cat Power)' is een credit, geen uitvoeringsversie.
        raw_value = re.sub(r'\s*\(with\s+[^()]+\)\s*$', '', raw_value,
                           flags=re.IGNORECASE)

        # Featuring-credit in de officiële Spotify-titel hoort niet bij
        # de muzikale kerntitel; de artiestenmetadata wordt apart getest.
        raw_value = re.sub(
            r"\s*\((?:feat\.?|ft\.?|featuring)\s+[^)]*\)",
            "",
            raw_value,
            flags=re.IGNORECASE
        )

        # v98: EP-aanduiding met een extra EP-naam ('Up Home EP version')
        # is dezelfde familie, zonder de genoemde EP-naam als een andere
        # song te behandelen. Versiecontrole blijft verplicht.
        raw_value = re.sub(
            r'(?i)\s*(?:-\s*)?\([^()]*\bep\s+version\)\s*$',
            '', raw_value
        ).strip()
        raw_value = re.sub(
            r'(?i)\s+-\s+[^-()]*\bep\s+version\s*$',
            '', raw_value
        ).strip()

        # Cataloguslabels die dezelfde opname/titel beschrijven.
        raw_value = re.sub(
            r"\s*\((?:[^)]*?\s+version|from\s+the\s+vault)\)",
            "",
            raw_value,
            flags=re.IGNORECASE
        )

        # Algemene versie-suffix: als een duidelijk afgescheiden laatste
        # segment door version_family() als versie wordt herkend, haal alleen
        # dat segment van de kerntitel af. Dit dekt bv. "Bright-Side Mix",
        # "Mandolin / Guitar Mix" en "Live at ..." zonder vrije fuzzy.
        if version_family(raw_value):
            if re.search(r"\s+-\s+[^()]+$", raw_value):
                raw_value = re.sub(r"\s+-\s+[^()]+$", "", raw_value).strip()
            elif re.search(r"\s*\([^()]+\)\s*$", raw_value):
                raw_value = re.sub(r"\s*\([^()]+\)\s*$", "", raw_value).strip()

        value = normalize(_numbered_title_equivalent(raw_value))

        # Officiële film-/soundtracktoevoeging.
        motion_picture_pattern = re.compile(
            r"(?:\s+|\[\s*|\(\s*)from\s+the\s+motion\s+picture\b.*(?:\]|\))?\s*$",
            re.IGNORECASE
        )

        value = motion_picture_pattern.sub(
            "",
            value
        ).strip()

        # v52.10: titelcontext van een HBO-serie, geen nieuwe uitvoering.
        # Alleen een VOLLEDIG afgescheiden catalogussuffix, niet willekeurige
        # titelwoorden; artiest- en versievergelijking blijven verplicht.
        value = re.sub(
            r'\s+-\s+from\s+[\"“”]?[^\"“”]+[\"“”]?\s+an\s+hbo\s+original\s+series\s*$',
            '', value, flags=re.IGNORECASE
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

    # v71: expliciet gecrediteerde gast in de radiotitel.
    with_credit = re.search(r'\(with\s+([^()]+)\)\s*$', str(title), flags=re.I)
    if with_credit and normalize(with_credit.group(1)) not in wanted_artists:
        wanted_artists.append(normalize(with_credit.group(1)))

    # Bewezen historische bandcredit is één artiestenidentiteit, niet
    # een verplichte extra gastartiest. Elders blijft de collab-regel streng.
    if re.sub(r"[^a-z0-9]+", " ", str(artist).casefold()).strip() == "liz cooper the stampede":
        wanted_artists = ["liz cooper"]

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
        if v88_radio_key == ("manassas", "colorado"):
            # Catalogus van Stephen Stills bevat veel Colorado-opnames.
            # RadioBox vraagt de opname uit het album Manassas.
            if (item.get("id") != "6VyuVYEJnZmlEQ5GT9LQvT"
                    or str((item.get("album") or {}).get("name", "")).casefold().strip() != "manassas"):
                continue
        # v72: een resultaat dat voor dit account niet speelbaar is,
        # nooit toevoegen. Spotify Search met market=from_token kan
        # is_playable=False of restrictions.reason=market teruggeven.
        # Ontbrekende velden betekenen niet automatisch 'onbeschikbaar'.
        if item.get("is_playable") is False:
            print(f"⏭️ Niet afspeelbaar in accountregio: {item.get('name', '')}")
            continue
        if (item.get("restrictions") or {}).get("reason") == "market":
            print(f"⏭️ Regionaal geblokkeerd: {item.get('name', '')}")
            continue
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

        # De primaire RadioBox-artiest mag alleen door Spotify-artiest #1
        # worden bevestigd. Een gastartiest op plaats 2+ mag de match niet redden.
        spotify_primary_artist = spotify_artists[0]
        spotify_primary_compact = compact(
            spotify_primary_artist
        )

        primary_artist_score = SequenceMatcher(
            None,
            primary_wanted_artist,
            spotify_primary_compact
        ).ratio()

        primary_artist_exact = (
            primary_wanted_artist
            == spotify_primary_compact
        )
        # v52.5: intern koppelteken versus spatie in DEZELFDE volledige
        # hoofdartiest is een schrijfvariant, geen andere artiest.
        # Bijvoorbeeld "Warrington Runcorn" en "Warrington-Runcorn".
        # Geen prefix-, gedeeltelijke of fuzzy match.
        if not primary_artist_exact:
            def _v525_artist_words(value):
                return re.sub(r"[-‐‑‒–—]", " ", value).split()
            if _v525_artist_words(primary_wanted_artist) == _v525_artist_words(spotify_primary_compact):
                primary_artist_exact = True
                primary_artist_score = 1.0

        # v51.8: expliciete gast in de RadioBox-titel kan in Spotify
        # de enige hoofdartiest zijn. Alleen EXACTE gastidentiteit,
        # precies één Spotify-artist en geen andere artiest.
        guest_only_catalog_match = bool(
            title_feature_artist
            and len(spotify_artists) == 1
            and compact(re.sub(r'["“”]', '', title_feature_artist))
                == compact(re.sub(r'["“”]', '', spotify_primary_artist))
        )
        if guest_only_catalog_match:
            primary_artist_exact = True
            primary_artist_score = 1.0

        # v51: correcte cataloguscredit kan extra sessiemuzikanten bevatten,
        # een bandnaam uitschrijven, of de artiest pas na een componist noemen.
        # Alleen identieke VOLLEDIGE namen tellen; definitieve titeltoets volgt.
        v51_credit_rescue = False
        v51_artist_parts = [alias_key(a) for a in spotify_artists]
        v51_requested = alias_key(wanted_artists[0])
        v51_splits = [alias_key(x) for x in re.split(
            r"\s+(?:&|and|with)\s+", wanted_artists[0]) if x.strip()]
        if len(spotify_artists) > 1:
            # Eén exact gecrediteerde artiest, naast componist of ensemble.
            if v51_requested in v51_artist_parts and len(spotify_artists) == 2:
                v51_credit_rescue = True
            # Echte samenwerkingen: beide volledige namen, volgorde onbelangrijk.
            elif len(v51_splits) == 2 and len(spotify_artists) == 2 and all(x in v51_artist_parts for x in v51_splits):
                v51_credit_rescue = True
            # Een project met 'A & B' waarvan Spotify A als hoofdartiest en
            # B als oorspronkelijke groepscredit weglaat: nog niet automatisch,
            # behalve wanneer overige artiesten als begeleiders vermeld staan.
            elif (len(v51_splits) == 2 and len(v51_splits[0]) >= 9
                  and v51_splits[0] == v51_artist_parts[0]
                  and v51_splits[1] not in v51_artist_parts
                  and len(spotify_artists) >= 3):
                v51_credit_rescue = True
        # v51.1: Spotify zet een solist soms onder een uitgebreide officiële
        # bandcredit, bv. "Ben Harper And The Innocent Criminals". Accepteer
        # uitsluitend de HELE naam plus een expliciete bandverbinding; een
        # gewone tekstprefix is nooit voldoende. Exacte titelcontrole volgt.
        v51_named_band_credit = False
        if len(wanted_artists) == 1 and len(spotify_artists) == 1:
            requested_tokens = alias_key(wanted_artists[0]).split()
            catalog_tokens = alias_key(spotify_artists[0]).split()
            if (len(requested_tokens) >= 2
                    and len(catalog_tokens) >= len(requested_tokens) + 2
                    and catalog_tokens[:len(requested_tokens)] == requested_tokens
                    and catalog_tokens[len(requested_tokens)] in {'and', 'with', '&'}
                    and len(catalog_tokens[len(requested_tokens)+1:]) >= 1):
                v51_named_band_credit = True
                primary_artist_score = 1.0
                primary_artist_exact = True
        # v71: 'Vince Guaraldi' -> 'Vince Guaraldi Trio' wordt alleen
        # toegestaan als de volledige eigennaam + expliciet 'Trio' klopt.
        if (len(spotify_artists) == 1
                and alias_key(spotify_artists[0]) == alias_key(wanted_artists[0]) + ' trio'):
            v51_credit_rescue = True

        if v51_credit_rescue:
            primary_artist_score = 1.0
            primary_artist_exact = True

        # v71: Spotify publiceert een project ook als band + afzonderlijke
        # leden. De VOLLEDIGE projectnaam moet de eerste Spotify-artiest
        # zijn; leden moeten exact onder de extra credits staan.
        project_members = re.match(r'^(.+?)\s*\(([^()]+)\)\s*$', str(artist))
        if project_members and len(spotify_artists) >= 2:
            if (alias_key(project_members.group(1)) == alias_key(spotify_artists[0])
                    and set(v71_credit_parts(project_members.group(2))).issubset(
                        {normalize_match(x) for x in spotify_artists[1:]})):
                primary_artist_exact = True
                primary_artist_score = 1.0
                v51_credit_rescue = True

        # v45: ALGEMENE regels voor Spotify-project- en samenwerkingscredits.
        # Geen artiest-/titel-specifieke uitzonderingen.
        #
        # 1. Een project mag zijn naam na de solist hebben, als de
        #    solonaam de volledige BEGINcomponent van de projectnaam is,
        #    gevolgd door een echte groepsverbinding (and/&/with).
        #    Bv. "Susanna" + "Susanna and the Magical Orchestra".
        # 2. Bij een EXPLICIET gevraagde gastartiest mag Spotify precies
        #    EEN aanvullende hoofdcredit vooraan zetten, mits de gevraagde
        #    hoofdartiest op plaats twee staat, alle gevraagde gasten verder
        #    exact vermeld staan, en de Spotify-titel de gast expliciet noemt.
        #    Bv. producer, primaire uitvoerder en expliciete zang-gast.
        #
        # Bij beide vormen blijven de bestaande volledige titel-, versie-,
        # ambiguïteits- en ISRC-controles verderop verplicht.
        def _credit_tokens(value):
            return alias_key(value).split()

        project_artist_credit = False
        if len(wanted_artists) == 1 and len(spotify_artists) == 2:
            solo_tokens = _credit_tokens(spotify_artists[0])
            band_tokens = _credit_tokens(spotify_artists[1])
            wanted_tokens = _credit_tokens(wanted_artists[0])
            if (len(solo_tokens) >= 1
                    and len(band_tokens) >= len(solo_tokens) + 2
                    and band_tokens[:len(solo_tokens)] == solo_tokens
                    and band_tokens[len(solo_tokens)] in {"and", "with"}
                    and band_tokens == wanted_tokens):
                project_artist_credit = True

        explicit_guest_credit = False
        if (title_feature_artist
                and len(wanted_artists) >= 2
                and len(spotify_artists) == len(wanted_artists) + 1
                and alias_key(spotify_artists[1]) == alias_key(wanted_artists[0])
                and all(alias_key(a) == alias_key(b)
                        for a, b in zip(spotify_artists[2:], wanted_artists[1:]))):
            spotify_raw_title = str(item.get("name") or "")
            # Een expliciete "feat. X" in de officiële tracktitel is de
            # onafhankelijke aanwijzing voor de genoemde gast, los van
            # Spotify's artist-array. Een loutere generieke titel volstaat niet.
            spotify_title_guest = re.search(
                r"\b(?:feat\.?|ft\.?|featuring|with)\s+([^()\[\],]+)",
                spotify_raw_title, flags=re.IGNORECASE)
            if (spotify_title_guest
                    and alias_key(spotify_title_guest.group(1))
                        == alias_key(title_feature_artist)):
                explicit_guest_credit = True

        # v46: bij een cover/tribute-album crediteert Spotify soms ook
        # de oorspronkelijke componist als derde artiest. Accepteer dat
        # alleen als beide gevraagde uitvoerders exact en in volgorde
        # aanwezig zijn EN het album de derde credit expliciet noemt in
        # "songs of X" of "tribute to X". Geen algemene extra-artiestvrijstelling.
        tribute_composer_credit = False
        if len(wanted_artists) == 1 and len(spotify_artists) == 3:
            wanted_pair = re.split(r"\s+(?:&|and)\s+", wanted_artists[0])
            album_credit = alias_key((item.get("album") or {}).get("name", ""))
            composer = alias_key(spotify_artists[2])
            if (len(wanted_pair) == 2
                    and all(alias_key(a) == alias_key(b)
                            for a, b in zip(wanted_pair, spotify_artists[:2]))
                    and composer
                    and (f"songs of {composer}" in album_credit
                         or f"tribute to {composer}" in album_credit)):
                tribute_composer_credit = True

        if project_artist_credit or explicit_guest_credit or tribute_composer_credit:
            primary_artist_score = 1.0
            primary_artist_exact = True

        # RadioBox may encode a collaboration as one `A & B` credit,
        # while Spotify exposes A and B as separate artists. Accept only
        # the EXACT ordered full credit, never a substring or missing guest.
        if len(spotify_artists) > 1:
            spotify_joint_credit = normalize(" & ".join(spotify_artists))
            wanted_joint_credit = normalize(wanted_artists[0])
            if spotify_joint_credit == wanted_joint_credit:
                primary_artist_score = 1.0
                primary_artist_exact = True

        # v40: Spotify may reverse two *complete* collaborator credits.
        # Require precisely the same two artist identities and no guests;
        # do not split band names unless Spotify actually supplies two artists.
        reversed_duo_match = False
        if len(spotify_artists) == 2 and len(wanted_artists) == 1:
            wanted_duo = re.split(r"\s+(?:&|and)\s+", wanted_artists[0])
            # v92: werk hier met de ORIGINELE RadioBox-credit: normalize()
            # verwijdert komma's en zet '&Tilly' om naar 'and tilly'.
            # Alleen 'A, &B' is een ondubbelzinnige twee-artiesten-credit.
            comma_ampersand_duo = re.fullmatch(
                r"\s*([^,]+?)\s*,\s*(&\s*[^,]+?)\s*",
                str(artist),
            )
            if comma_ampersand_duo:
                wanted_duo = [comma_ampersand_duo.group(1),
                              comma_ampersand_duo.group(2)]
            if (len(wanted_duo) == 2
                    and all(compact(name) for name in wanted_duo)
                    and {compact(name) for name in wanted_duo}
                        == {compact(name) for name in spotify_artists}
                    and compact(wanted_duo[0]) != compact(wanted_duo[1])):
                reversed_duo_match = True
                primary_artist_exact = True
                primary_artist_score = 1.0

        # v98: exacte 2+ credit-set, ook voor `A, B & C` en omgekeerde
        # volgorde. Geen ontbrekende gast / geen fuzzy artiestenvergelijking.
        if (len(wanted_artists) == 1
                and v98_exact_collaboration(artist, spotify_artists)):
            primary_artist_exact = True
            primary_artist_score = 1.0
            v51_credit_rescue = True

        # v98: originele spelling letterlijk in haakjes achter Spotify-
        # artiestnaam (bv. niet-Latijns schrift + transliteratie).
        if (len(wanted_artists) == 1
                and v98_parenthetical_artist_alias(
                    wanted_artists[0], spotify_artist_objects[0].get("name", ""))):
            primary_artist_exact = True
            primary_artist_score = 1.0

        # v98: in klassieke muziek kan Spotify de uitvoerders als artiesten
        # tonen, met de componist uitsluitend in de VOLLEDIGE werktitel.
        # De strenge werk+deelvergelijking hieronder blijft verplicht.
        v98_performer_classical_credit = bool(
            v98_classical_movement_key(title)
            and v98_classical_movement_key(title)
                == v98_classical_movement_key(item.get('name', ''))
            and v98_classical_composer_in_title(
                wanted_artists[0], item.get('name', ''))
        )
        if v98_performer_classical_credit:
            primary_artist_exact = True
            primary_artist_score = 1.0
            v51_credit_rescue = True

        # v98: een artiest met exact dezelfde volledige naam kan later
        # als gast op soundtrackcredits staan. Alleen het VOLLEDIGE
        # kernnummer mag matchen; nooit een andere titel of vage substring.
        v98_credit_at_any_position = bool(
            len(wanted_artists) == 1 and len(spotify_artists) >= 3
            and compact(wanted_artists[0]) in spotify_artist_compact
        )
        if v98_credit_at_any_position:
            primary_artist_exact = True
            primary_artist_score = 1.0
            v51_credit_rescue = True

        # v30: RadioBox kan een samenwerking als "A & B" schrijven,
        # terwijl Spotify alleen A als primaire artiest heeft. Dit is
        # uitsluitend een solo-fallback bij exacte A-credit; geen fuzzy prefix.
        # Officiële bandnamen blijven beschermd tegen splitsen.
        possible_collab = re.split(r"\s+(?:&|and)\s+", wanted_artists[0])
        solo_collab_fallback = False
        # v72: 'Angus & Julia Stone', 'Simon & Garfunkel' en andere
        # officiële duo-/bandnamen mogen NOOIT stilzwijgend als een
        # solo-opname van het eerste naamdeel worden goedgekeurd.
        # Volledige bandcredit of aantoonbaar afzonderlijke Spotify-
        # artist objects blijven geldig (reversed_duo_match hierboven).

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

        spotify_without_the = without_leading_the(
            spotify_primary_artist
        )

        if spotify_without_the:
            the_artist_score = SequenceMatcher(
                None,
                wanted_without_the,
                spotify_without_the
            ).ratio()

            primary_artist_score = max(
                primary_artist_score,
                the_artist_score
            )

            if wanted_without_the == spotify_without_the:
                primary_artist_exact = True

        # Een expliciet bekende naamswijziging mag de oude
        # artiestnaam koppelen aan de actuele Spotify-naam.
        alias_artist_match = (
            alias_key(spotify_primary_artist)
            in {
                alias_key(alias)
                for alias in search_artist_aliases
            }
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
            spotify_name_parts = normalize(
                spotify_primary_artist
            ).split()

            if len(spotify_name_parts) == 2:
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
        # Do not grant ownership from arbitrary substrings, even if Spotify's
        # artist is shorter. Only previously confirmed catalog aliases survive.
        confirmed_project_aliases = {
            ("j s ondara", "ondara"),
            ("liz cooper the stampede", "liz cooper"),
            ("stevie ray vaughan and double trouble", "stevie ray vaughan"),
        }
        primary_artist_contained = (
            (alias_key(wanted_artists[0]), alias_key(spotify_artists[0]))
            in confirmed_project_aliases
        )

        if primary_artist_contained:
            # Exact bewezen projectalias krijgt dezelfde identiteit als de
            # gewone artiest, zonder algemene substring-tolerantie.
            primary_artist_score = 1.0
            primary_artist_exact = True

        # v38: Strength in Numbers wordt bij Spotify als losse bandleden
        # gecrediteerd. Alleen de bekende vijf leden, zonder vreemde artiesten.
        if alias_key(wanted_artists[0]) == "strength in numbers":
            band_members = {
                "bela fleck", "jerry douglas", "sam bush",
                "mark o connor", "edgar meyer",
            }
            artist_credits = {alias_key(a) for a in spotify_artists}
            if (len(artist_credits) >= 2
                    and artist_credits <= band_members
                    and "bela fleck" in artist_credits
                    and "jerry douglas" in artist_credits):
                primary_artist_score = 1.0
                primary_artist_exact = True

        # v38: bij dit klassieke werk vermeldt Spotify de componist als
        # eerste artiest, gevolgd door de door RadioBox genoemde uitvoerder.
        # Geen generieke vrijstelling voor alle Bach-opnames.
        if (alias_key(wanted_artists[0]) == "jimin oh havenith"
                and "prelude in c major" in str(title).casefold()
                and "bach" in str(title).casefold()
                and spotify_artist_compact
                and alias_key(spotify_artists[0]) == "johann sebastian bach"
                and any(alias_key(a) == "jimin oh havenith" for a in spotify_artists[1:])):
            primary_artist_score = 1.0
            primary_artist_exact = True

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
            and not solo_collab_fallback
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

            if feature_score >= 0.98 or any(
                wanted_feature == spotify_artist
                for spotify_artist in spotify_artist_compact
            ):
                matched_feature_count += 1

        # v30: een soloversie is een fallback, nooit de eerste keuze.
        # Een ONJUISTE gastcredit is geen soloversie en blijft verboden.
        explicit_feature_count = max(0, len(wanted_artist_compact) - 1)
        missing_feature_count = max(0, explicit_feature_count - matched_feature_count)
        if guest_only_catalog_match:
            # De gast is de enige Spotify-hoofdartiest; de vermelde
            # RadioBox-hoofdartiest ontbreekt. Dit is een zwakkere
            # match dan wanneer de volledige samenwerking aanwezig is.
            missing_feature_count = 0
        if missing_feature_count:
            if (not primary_artist_exact
                    or len(spotify_artists) != 1):
                continue
        feature_tier = 1 if explicit_feature_count and not missing_feature_count else 0
        # Spotify kan A & B ook als één gezamenlijke artiestnaam bewaren.
        # Deze exacte credit moet dan boven de A-solo-fallback staan.
        if (len(wanted_artists) == 1 and not missing_feature_count
                and len(re.split(r"\s+(?:&|and)\s+", wanted_artists[0])) == 2
                and primary_wanted_artist == spotify_primary_compact):
            feature_tier = 1
        # De volledige A & B-credit, verdeeld over twee Spotify-artists,
        # krijgt ook altijd voorrang op de soloversie.
        if len(spotify_artists) > 1 and primary_artist_exact and not missing_feature_count:
            if normalize(" & ".join(spotify_artists)) == normalize(wanted_artists[0]):
                feature_tier = 1

        # Bij een gecombineerde RadioBox-credit moet de solo-fallback
        # expliciet lager scoren dan dezelfde track met alle credits.
        if solo_collab_fallback:
            feature_tier = 0
            primary_artist_score = 1.0
            primary_artist_exact = True

        # =============================================
        # TITEL CONTROLEREN
        # =============================================

        # v38: een Lennon-solo-opname met extra koor-/orkestcredits is
        # niet de gewenste gewone Lennon-opname.
        if (alias_key(wanted_artists[0]) == "john lennon"
                and len(wanted_artists) == 1
                and len(spotify_artists) > 1):
            continue

        spotify_title = normalize(
            item.get("name", "")
        )

        if not spotify_title:
            continue

        spotify_title_base = title_base(
            item.get("name", "")
        )

        spotify_version = spotify_candidate_version(item)

        # v94: a radio title without an explicit live request must never
        # resolve to a bootleg concert recording (even as last-resort fallback).
        # An explicitly requested live recording keeps the established rules.
        candidate_name = str(item.get("name", "") or "")
        candidate_album = str((item.get("album") or {}).get("name", "") or "")
        if wanted_version != "live" and (
            re.search(r"\bbootleg\b", candidate_name, flags=re.IGNORECASE)
            or (spotify_version == "live" and re.search(
                r"\bbootleg\b", candidate_album, flags=re.IGNORECASE
            ))
        ):
            continue

        # "Soccer Mommy Version" <-> "Soccer Mommy Cut":
        # alleen equivalent als de benoemde variantnaam exact gelijk is.
        def named_variant_label(value):
            raw_variant = str(value or "").strip()
            raw_variant = raw_variant.replace("–", "-").replace("—", "-")

            # v52.10: drie veilige metadata-varianten; de naam/jaargang
            # van een benoemde versie blijft identiek vereist, ook wanneer
            # Spotify er de onschuldige catalogustag From The Vault na zet.
            match = re.search(
                r"\(([^()]+?)\s+version\)(?:\s*\(from\s+the\s+vault\))?\s*$",
                raw_variant,
                flags=re.IGNORECASE
            )
            if not match:
                # Benoemde versie na een dash is dezelfde variant als
                # dezelfde naam in haakjes: '(1973 Version)' = '- 1973 version'.
                # De bestaande varianttoets vergelijkt de volledige naam;
                # verschillende jaren/benamingen blijven uitgesloten.
                match = re.search(
                    r"\s+-\s+([^()]+?)\s+version\s*$",
                    raw_variant,
                    flags=re.IGNORECASE
                )
            if not match:
                match = re.search(
                    r"\s+-\s+(.+?)\s+cut\s*$",
                    raw_variant,
                    flags=re.IGNORECASE
                )

            if not match:
                return None

            label = normalize(match.group(1))
            if label in {
                "album", "single", "original", "deluxe",
                "radio", "acoustic", "live",
            }:
                return None
            return label or None

        wanted_named_variant = named_variant_label(title)
        spotify_named_variant = named_variant_label(
            item.get("name", "")
        )

        if (
            wanted_named_variant
            and spotify_named_variant != wanted_named_variant
            # Een onbenoemde EP-version mag aan een benoemde EP gekoppeld
            # worden; een gevraagde specifieke EP-naam nooit aan een andere.
            and not (wanted_named_variant == 'ep'
                     and spotify_named_variant
                     and spotify_named_variant.endswith(' ep'))
        ):
            continue

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
        wanted_title_for_match, _ = split_title_feature(search_title)

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

        # Sommige RadioBox-titels zijn door de bron zichtbaar ingekort,
        # bv. "Brushes (Never Going Back...)". Alleen wanneer de bron
        # letterlijk op een ellipsis eindigt en een lang, identiek
        # titelbegin aanwezig is, erkennen we de volledige Spotify-titel.
        # Geen fuzzy prefixmatch voor complete, niet-afgekorte titels.
        def explicit_ellipsis_match(radio_title, catalog_title):
            radio = str(radio_title or "").strip().casefold()
            catalog = str(catalog_title or "").strip().casefold()
            if not re.search(r"(?:\.{3}|…)[)\]\s]*$", radio):
                return False
            prefix = re.sub(r"(?:\.{3}|…)[)\]\s]*$", "", radio).rstrip()
            # Interpunctie verschillen normaliseren zonder woorden te verliezen.
            def words(text):
                return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", text))
            prefix_words = words(prefix)
            catalog_words = words(catalog)
            if len(prefix_words) < 4 or len("".join(prefix_words)) < 18:
                return False
            return catalog_words[:len(prefix_words)] == prefix_words

        truncated_title_match = (
            primary_artist_exact
            and explicit_ellipsis_match(wanted_title_for_match, item.get("name", ""))
        )

        structural_title_match = (
            truncated_title_match
            or wanted_identity == spotify_identity
            or wanted_base_identity == spotify_base_identity
            or optional_the_equivalent(
                wanted_title_base_for_match,
                spotify_title_base
            )
            or initial_transliteration_equivalent(
                wanted_title_base_for_match,
                spotify_title_base
            )
            or aka_title_equivalent(
                wanted_title_base_for_match,
                spotify_title_base
            )
            or (
                primary_artist_exact
                and leading_preposition_equivalent(
                    wanted_title_base_for_match,
                    spotify_title_base
                )
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

        # v51: symmetrische verklarende bron-toevoeging. Alleen als de
        # Spotify-titel precies gelijk is aan het volledige hoofdtiteldeel.
        # NOOIT gewone artist/title-prefixmatching of versieaanduidingen.
        def v51_descriptive_parenthesis(long_title, short_title):
            raw = str(long_title or '').strip()
            m = re.fullmatch(r'(.{7,}?)\s*\(([^()]{{4,75}})\)'.replace('{{','{').replace('}}','}'), raw)
            if not m or requested_version(raw):
                return False
            core, description = m.groups()
            if re.search(r'(?i)\b(?:live|acoustic|remix|mix|demo|edit|version|instrumental|session|take)\b', description):
                return False
            return title_compact(core) == title_compact(short_title)

        v51_descriptive_title_match = (
            primary_artist_exact and
            (v51_descriptive_parenthesis(wanted_title_for_match, spotify_title)
             or v51_descriptive_parenthesis(spotify_title, wanted_title_for_match))
        )
        if v51_descriptive_title_match:
            structural_title_match = True

        # v101: Britse/Amerikaanse schrijfwijze + eindinterpunctie.
        # Geen substring- of fuzzy-ontheffing: volledige kerntitel moet gelijk
        # zijn EN de hoofdartiest moet al exact gevalideerd zijn.
        if (primary_artist_exact and
                v101_safe_title_spelling(wanted_title_base_for_match)
                == v101_safe_title_spelling(spotify_title_base)):
            structural_title_match = True

        # v51: klassieke catalogi draaien werknaam en deel om en noemen
        # eventueel toonsoort/componist in de titel. Alleen dezelfde
        # instrumentale suite, hetzelfde nummer en exact dezelfde beweging.
        def v51_classical_equivalent(left, right):
            def identity(text):
                text = normalize(text)
                words = re.findall(r"[a-z0-9]+", text)
                if not ('cello' in words and 'suite' in words and 'prelude' in words):
                    return None
                n = re.search(r"(?:suite\s+(?:no\s*)?|suite\s*#\s*|suite\s*)([1-6])\b", text)
                if not n:
                    return None
                return ('cello suite', n.group(1), 'prelude')
            a, b = identity(left), identity(right)
            return a is not None and a == b

        v51_classical_title_match = (
            primary_artist_exact and
            v51_classical_equivalent(wanted_title_for_match, spotify_title)
        )
        if v51_classical_title_match:
            structural_title_match = True

        # v98: conservatieve klassieke muziek-metadata. Hetzelfde werk,
        # seizoen en deel zijn verplicht. Alleen als de volledige
        # opgegeven componist een Spotify-credit is. Welke uitvoering
        # RadioBox bedoelde, blijft zonder performer in bron onbekend.
        v98_classical_equivalent = (
            primary_artist_exact
            and v98_classical_movement_key(wanted_title_for_match) is not None
            and v98_classical_movement_key(wanted_title_for_match)
                == v98_classical_movement_key(spotify_title)
        )
        if v98_classical_equivalent:
            structural_title_match = True

        # v40: a catalog may prefix a FULL song title with "Theme from".
        # Only permit complete equality of the remaining title (at least
        # two words); never a partial title or an arbitrary soundtrack title.
        def full_theme_from_equivalent(left, right):
            def theme_words(value):
                words = normalize(value).split()
                return [re.sub(r"[^a-z0-9]", "", word) for word in words]

            lhs, rhs = theme_words(left), theme_words(right)
            for longer, shorter in ((lhs, rhs), (rhs, lhs)):
                if (len(shorter) >= 2
                        and longer[:2] == ["theme", "from"]
                        and longer[2:] == shorter):
                    return True
            return False

        theme_title_match = (
            primary_artist_exact
            and full_theme_from_equivalent(
                wanted_title_base_for_match, spotify_title_base
            )
        )

        # v71: beperkte catalogustitel-correctie; korte algemene titels
        # worden buiten dit bevestigde duo NOOIT prefixgewijs gekoppeld.
        if (primary_artist_exact and
                v71_same_song_title(wanted_title_for_match, item.get('name', ''), artist)
                and wanted_base_compact != spotify_base_compact):
            structural_title_match = True

        # Confidence-klassen zijn belangrijker dan een klein scoreverschil.
        # Een fuzzy kandidaat mag zo nooit een structureel exactere match
        # voorbijsteken door toevallige artiest-/featurebonussen.
        if spotify_compact == wanted_compact:
            title_score = 1.0
            title_confidence = 5

        # Veilige vormvarianten (separator/datum/quote/optioneel "the").
        elif structural_title_match or theme_title_match:
            title_score = 0.997
            title_confidence = 4

        # Exacte basistitel na bekende versie-aanduiding.
        elif spotify_base_compact == wanted_base_compact:
            title_score = 0.99
            title_confidence = 3

        # RadioBox kan een officiële verklarende suffix weglaten.
        elif extension_title_match:
            title_score = 0.985
            title_confidence = 2

        else:
            title_confidence = 1
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

        # v52.10: een enkele letterfout in een INTERNE titelterm mag
        # dezelfde opname zijn als hoofdartiest en volledige versie EXACT
        # kloppen. Eerste en laatste woord zijn identiek; minimaal 3 woorden,
        # minimaal 12 tekens; geen vrije fuzzy titel- of artiestmatch.
        if title_confidence == 1 and primary_artist_exact \
                and wanted_version == spotify_version:
            _ww = wanted_title_base_for_match.split()
            _sw = spotify_title_base.split()
            if (len(_ww) == len(_sw) and len(_ww) >= 3
                    and len(wanted_base_compact) >= 12
                    and _ww[0] == _sw[0] and _ww[-1] == _sw[-1]):
                _different = [(a, b) for a, b in zip(_ww, _sw) if a != b]
                if (len(_different) == 1
                        and len(_different[0][0]) == len(_different[0][1])
                        and sum(a != b for a, b in zip(*_different[0])) == 1):
                    structural_title_match = True
                    title_score = 0.997
                    title_confidence = 4

        # v51.8: guest-only catalogusmatch uitsluitend bij dezelfde
        # COMPLETE kerntitel. Geen fuzzy overeenkomst en geen
        # gedeeltelijke/verkorte titel; dit voorkomt verkeerde covers.
        if guest_only_catalog_match and not (
            spotify_compact == wanted_compact
            or spotify_base_compact == wanted_base_compact
        ):
            continue

        # v51: een artiest op een andere creditpositie is uitsluitend veilig
        # als de VOLLEDIGE hoofd- of kerntitel gelijk is; nooit fuzzy titels.
        if (v51_credit_rescue or v51_named_band_credit) and not (
            spotify_compact == wanted_compact
            or spotify_base_compact == wanted_base_compact
            or structural_title_match
            # Ook bij een extra officiële verklarende ondertitel blijft
            # de volledige hoofdtitel exact verplicht, geen substring.
            or (primary_artist_exact and extension_title_match)
        ):
            continue

        # Korte/generieke titels zijn het gevaarlijkst: "Home", "Stay",
        # "Run", "You" enz. mogen niet op een middelmatige fuzzy match landen.
        # Exacte/structurele matches vallen hier niet onder.
        wanted_word_count = len([w for w in normalize(wanted_title_base_for_match).split() if w])
        wanted_identity_len = len(wanted_base_identity)
        if title_confidence == 1:
            if wanted_word_count <= 2 or wanted_identity_len <= 8:
                if title_score < 0.97 or primary_artist_score < 0.97:
                    continue
            elif wanted_word_count == 3:
                if title_score < 0.945 or primary_artist_score < 0.94:
                    continue

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
            + (matched_feature_count * 0.12)
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

        candidate_score -= missing_feature_count * 0.12

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
        # v30: gevraagde versie eerst; overige betrouwbare uitvoeringen
        # alleen volgens de vastgelegde fallback-prioriteit.
        # Specifieke benoemde versies en concertlocaties blijven beschermd.
        hard_alternative_versions = {
            "live", "mix", "remix", "acoustic", "demo",
            "instrumental", "reprise", "alternate", "spotify singles",
            "unplugged", "stripped", "session", "take", "mono", "stereo",
            "extended", "piano version", "orchestral version",
            "re-recorded", "sped up", "slowed", "nightcore", "karaoke",
        }
        soft_fallback_versions = {
            "edit", "single version", "album version", "version",
            "bonus track",
        }

        same_core_title = (
            spotify_compact == wanted_compact
            or spotify_base_compact == wanted_base_compact
            or structural_title_match
            or extension_title_match
        )

        # v51.5: gevraagde familie eerst; vervolgens door de gebruiker
        # vastgelegde fallbackvolgorde. Eén Spotify Search blijft één call.
        # "acoustic"/"demo"/"instrumental" krijgen uitsluitend een
        # exacte match: die zijn niet gelijk aan gewone/live-opnames.
        if wanted_named_variant and spotify_named_variant != wanted_named_variant:
            # Alleen onbenoemde EP-versie mag matchen met benoemde EP.
            if not (wanted_named_variant == 'ep'
                    and spotify_named_variant
                    and spotify_named_variant.endswith(' ep')):
                continue

        def preferred_family(family):
            if family in (None, "ordinary", "original version", "album version",
                          "single version", "version", "bonus track"):
                return "ordinary"
            if family == "remaster":
                return "remaster"
            if family == "live":
                return "live"
            if family in ("mix", "remix"):
                return "mix"
            return family

        wanted_family = preferred_family(wanted_version)
        candidate_family = preferred_family(spotify_version)
        preferred_order = {
            "ordinary": ["ordinary", "remaster", "ep version", "edit", "edition", "acoustic", "unplugged", "stripped", "spotify singles", "session", "live", "demo", "alternate", "take", "re-recorded", "piano version", "orchestral version", "instrumental", "extended", "mono", "stereo", "mix", "remix", "named version"],
        }
        # Catalogus-/sessieopnames zijn een laatste redmiddel, GEEN gewone
        # studioversies. Bijvoorbeeld "Flume - Spotify Singles" bij FINNEAS.
        # Alleen toelaten als de hoofdartiest en volledige kerntitel exact
        # overeenkomen; de vier bestaande opnamevoorkeuren blijven voorop.
        session_fallbacks = {"spotify singles", "session"}
        # v75: de gewone uitvoering gaat ALTIJD voor, ook als de radio
        # een speciale versie vermeldt. Daarna veilige officiële alternatieven.
        if wanted_family != "ordinary":
            preferred_order[wanted_family] = preferred_order["ordinary"]
        if wanted_family in preferred_order:
            order = preferred_order[wanted_family]
            if candidate_family in session_fallbacks:
                if not primary_artist_exact or not same_core_title or (
                    spotify_base_compact != wanted_base_compact
                ):
                    continue
                version_tier = len(order)
            elif candidate_family in order:
                # Onbekende benoemde versie alleen als de basis ECHT exact is.
                if candidate_family == "named version" and (
                    not primary_artist_exact or spotify_base_compact != wanted_base_compact
                ):
                    continue
                version_tier = order.index(candidate_family)
            else:
                continue
            # Gewenste familie gaat vóór credit-tier bij al veilig bevonden matches.
        else:
            # Specifieke uitvoeringen die de gebruiker niet als een van de vier
            # fallbackfamilies heeft beschreven strikt blijven matchen.
            if spotify_version != wanted_version:
                continue
            version_tier = 0

        if candidate_family == wanted_family:
            candidate_score += 0.60
        elif candidate_family == "ordinary":
            candidate_score += 0.30
        elif candidate_family == "remaster":
            candidate_score += 0.24
        elif candidate_family == "live":
            candidate_score -= 0.35
        elif candidate_family == "mix":
            candidate_score -= 0.50

        # Preserve v29's strong fallback checks: a loose title or artist
        # resemblance must never become valid only because of a version suffix.
        if version_tier and (not same_core_title or primary_artist_score < 0.98):
            continue
        if spotify_version == "arrangement" and not wanted_version:
            continue
        if spotify_version in soft_fallback_versions and not wanted_version:
            if title_score < 0.985 or primary_artist_score < 0.95:
                continue
        if spotify_version == "original version" and not wanted_version:
            if not same_core_title or primary_artist_score < 0.95:
                continue
        if spotify_version == "named version" and not wanted_named_variant:
            # v75: alleen veilig als volledige kern én hoofdartiest exact zijn.
            if not primary_artist_exact or spotify_base_compact != wanted_base_compact:
                continue
        # Een solo-collab fallback mag nooit een slecht passende titel redden.
        if (solo_collab_fallback or missing_feature_count) and (
            not same_core_title or spotify_base_compact != wanted_base_compact
        ):
            continue

        candidate_isrc = str(
            (item.get("external_ids") or {}).get(
                "isrc",
                ""
            )
        ).strip().upper() or None

        match_reason = {
            5: "exact title",
            4: "structural title",
            3: "exact core title",
            2: "safe catalog suffix",
            1: "high-confidence fuzzy",
        }[title_confidence]

        candidates.append(
            (
                -version_tier,
                feature_tier,
                title_confidence,
                candidate_score,
                -len(candidates),
                item.get("uri"),
                candidate_isrc,
                item.get("name", ""),
                ", ".join(a.get("name", "") for a in spotify_artist_objects),
                match_reason,
                spotify_version or "ordinary",
            )
        )

    if candidates:
        candidates.sort(
            key=lambda candidate: (
                candidate[0],  # requested version order (only safe matches reach this stage)
                candidate[1],  # complete artist/featured credits within version
                candidate[2],  # title confidence class
                candidate[3],  # detailed score
                candidate[4],  # Spotify order tie-break
            ),
            reverse=True
        )

        # Als twee verschillende opnames praktisch gelijk scoren binnen
        # dezelfde confidence- en versieklasse: liever overslaan dan gokken.
        # Dezelfde ISRC is echter dezelfde opname op een andere release en
        # mag dus nooit kunstmatige ambiguïteit veroorzaken.
        if len(candidates) > 1:
            best, second = candidates[0], candidates[1]
            same_recording = bool(best[6] and second[6] and best[6] == second[6])

            # Meerdere officiële varianten van exact dezelfde kerntitel binnen
            # dezelfde fallback-familie (bv. Bright-Side Mix / Dark-Side Mix)
            # zijn geen song-ambiguïteit. Als er geen ordinary/remaster/edit
            # beschikbaar is, mag Spotify's eigen ranking de variant kiezen.
            same_core_variant_family = (
                best[10] == second[10]
                and best[10] in hard_alternative_versions
                and title_identity(title_base(best[7])) == title_identity(title_base(second[7]))
            )

            if (
                not same_recording
                and not same_core_variant_family
                and best[5] != second[5]
                and best[0] == second[0]
                and best[1] == second[1]
                and best[2] == second[2]
                and abs(best[3] - second[3]) < 0.015
                and best[3] < 2.40
            ):
                return None

        LAST_SPOTIFY_MATCH_METADATA = (candidates[0][8], candidates[0][7])
        LAST_SPOTIFY_MATCH_ISRC = candidates[0][6]
        print(
            "🎯 Spotify match gekozen: "
            f"{candidates[0][8]} — {candidates[0][7]} "
            f"| {candidates[0][9]} | versie: {candidates[0][10]}"
        )
        return candidates[0][5]

    print(f"🧭 v80 matcher-diagnose: {v80_failure_reason(items, artist, title)} | zoekstrategie={search_variant}")
    print(f"🧭 v82 afwijsreden: {v82_match_diagnosis(items, artist, title)} | zoekstrategie={search_variant}")
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

    # Laatste beveiliging: ook cache/locator mag geblokkeerde opname niet toevoegen.
    blocked = [uri for uri in uris if is_blocked_german_spotify_uri(uri)]
    if blocked:
        raise RuntimeError("v102: geblokkeerde Duitstalige Spotify-opname; niet toegevoegd.")

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
    # Unicode-okina en modifier-apostrof zijn catalogus-schrijfvarianten.
    value = value.replace("ʻ", "'").replace("ʼ", "'").replace("’", "'")

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


def v71_credit_parts(value):
    """Volledige samenwerkingscredits, zonder een bandnaam zomaar te splitsen."""
    import re
    raw = str(value or '').strip()
    raw = re.sub(r'\s*\(\s*([^()]+?)\s*\)\s*$',
                 lambda m: ' & ' + m.group(1) if re.search(r'(?i)\b(?:and|&|with)\b', m.group(1)) else m.group(0), raw)
    raw = re.sub(r'(?i)\s+\b(?:feat\.?|ft\.?|featuring|with|w/)\s+', ' & ', raw)
    return [normalize_match(x) for x in re.split(r'\s+(?:&|and)\s+|\s*,\s*', raw) if normalize_match(x)]


def v71_core_song_title(value):
    """Alleen duidelijk afgescheiden uitvoeringslabels verwijderen."""
    import re
    raw = str(value or '').strip()
    raw = re.sub(r'(?i)\s*\((?:with|feat\.?|featuring|ft\.?)\s+[^()]+\)\s*$', '', raw)
    suffix = r'(?:\d{4}\s+)?(?:remaster(?:ed)?(?:\s+version)?|live(?:\s+(?:at|in|from)\s+.+)?|acoustic(?:\s+version)?|studio(?:\s+version)?|(?:radio|club|extended|album|single|original)\s+(?:mix|edit|version)|remix|mix|version)'
    old=None
    while old != raw:
        old=raw
        raw=re.sub(r'\s*(?:\(\s*'+suffix+r'\s*\)|\s+[-–—]\s+'+suffix+r')\s*$', '', raw, flags=re.I).strip()
    return normalize_match(raw)


def v71_same_song_title(a, b, artist=''):
    left, right = v71_core_song_title(a), v71_core_song_title(b)
    if left == right:
        return bool(left)
    # Eén expliciet bevestigde RadioBox-verkorting; niet generiek
    # 'Someone' aan 'Someone Else' gelijkstellen.
    known = {'eskobar & heather nova', 'eskobar and heather nova'}
    if normalize_match(artist) in known:
        return {left, right} == {'someone', 'someone new'}
    # v76: dezelfde bewezen RadioBox-correctie voor de duplicaatcontrole.
    # Enkel Jackson Browne; geen algemene For Everyman / To Me-fuzzy match.
    # v77: expliciet bevestigde catalogusverschillen, ook in de
    # duplicaatcontrole. Enkel dezelfde volledige artiest + titelpaar.
    confirmed = {
        'don williams': ({'till the rivers run dry', 'till the rivers all run dry'},),
        'prince': ({'affirmations way back home', 'way back home'},),
    }
    comparable = lambda x: normalize_match(x).replace("'", "").lstrip()
    artist_key = comparable(artist)
    title_pair = {comparable(left), comparable(right)}
    if any(title_pair == set(pair) for pair in confirmed.get(artist_key, ())):
        return True
    if normalize_match(artist) == 'jackson browne':
        if {left, right} == {'sing my songs for everyman', 'sing my songs to me'}:
            return True
    return False


def v71_same_artist_credit(requested, candidate):
    """Bandnaam exact OF volledige gedeelde samenwerking, geen substring."""
    a, b = normalize_match(requested), normalize_match(candidate)
    if a == b:
        return True
    parts_a = v71_credit_parts(requested)
    parts_b = v71_credit_parts(candidate)
    # Eén hoofdartiest plus extra Spotify-gasten is toegestaan;
    # omgekeerd alleen bij volledige expliciete samenwerking.
    return bool(parts_a and parts_b and (
        (len(parts_a) > 1 and set(parts_a).issubset(set(parts_b)))
        or (len(parts_a) == 1 and parts_a[0] == parts_b[0])
    ))


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

    # Alleen de primaire Spotify-artiest krijgt een individuele key.
    # Gastartiesten blijven beschikbaar in de gecombineerde keys.
    if artists:
        keys.add(f"{artists[0]}|||{title}")

    # Gecombineerde vorm: alle Spotify-artiesten samen.
    if artists:
        combined = "|||".join(artists)
        keys.add(f"{combined}|||{title}")

    # Extra gecombineerde vorm met " & ".
    if artists:
        combined_amp = " & ".join(artists)
        keys.add(f"{combined_amp}|||{title}")

    # v71: een nummer mag maar één versie in de playlist hebben.
    # De bestaande volledige metadata-keys blijven behouden.
    core_title = v71_core_song_title(track.get('name', ''))
    if core_title and artists:
        keys.add(f"{artists[0]}|||{core_title}")
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

    # v71: deel dezelfde lied-identiteit over gewone, live-, remaster-
    # en mixversies. Een Spotify-song met een andere ISRC is geen reden
    # om hetzelfde lied opnieuw toe te voegen.
    for key in playlist_keys:
        if '|||' not in key:
            continue
        saved_artist, saved_title = key.split('|||', 1)
        if v71_same_song_title(playlist_match_title, saved_title, artist_text) and (
            any(v71_same_artist_credit(a, saved_artist) for a in radio_artists)
            or v71_same_artist_credit(artist_text, saved_artist)
        ):
            return True

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




# v48: Alleen duidelijke interview-fragmenten blokkeren. Geen gewone
# muziektitels met het woord "interview" midden in de titel uitsluiten.
def is_interview_fragment(title):
    title = str(title or "").strip()
    title = re.sub(r"^[\s\[\(]*", "", title)
    # v52.2: duidelijke archief-placeholders filteren vóór de Spotify Search.
    if re.fullmatch(
        r"(?i)\s*(?:unknown[ -]+(?:song|track|title)|(?:song|track|title)[ -]+unknown|"
        r"onbekend[ -]+nummer|nummer[ -]+onbekend|onbekende[ -]+titel|"
        r"(?:no|geen)[ -]+(?:song[ -]+)?title)\s*",
        title,
    ):
        return True
    if re.fullmatch(r"(?i)\s*(?:sessie|session|interview\s*[+&]\s*sessie)\s*", title):
        return True
    return bool(re.match(
        r"(?i)^interview(?:\s*(?:\(|\[|:|[-–—]|with\b|met\b|w/\b|\d{1,3}\b)|\s*$)",
        title,
    ))


# v47: RadioBox-ingestie en herprobeerbare missers zonder extra Spotify Search.
def _v47_key(artist, title):
    return f"{normalize_match(artist)}|||{normalize_match(title)}"


def v47_collect_radio_history(radio_sources, cache, seen, live_queue, matching_version=34):
    """Ingest every visible unique RadioBox track, without spending Spotify Search.

    Persistently register each observed title, so repeats do not use extra work.
    Never mark an unsuccessful search as completed: failed items live in a
    separate retry register until they can be retried.
    """
    discovered = cache.setdefault("__v47_radio_discovered", {})
    # v69: bij nieuwe start: markeer bestaande zichtbare RadioBox-historiek
    # als reeds gezien. Enkel het nú gespeelde nummer per bron is nieuw.
    # v93: scan na bootstrap de volledige zichtbare historiek zodat ook
    # tussen twee controles uitgezonden nummers geregistreerd worden.
    if cache.get("__v69_radio_only_fresh_start") and not cache.get("__v69_bootstrap_complete"):
        # Bij tijdelijke RadioBox-storing geen lege beginmeting vastleggen.
        if any(not src.get("tracks") for src in radio_sources):
            print("⏳ v69: eerste RadioBox-meting onvolledig; wacht op beide zenders.")
            return 0
        for src in radio_sources:
            tracks = src.get("tracks", [])
            existing = {_v47_key(a, t) for a, t in tracks[1:] if a and t}
            discovered[src["id"]] = sorted(existing)
        cache["__v69_bootstrap_complete"] = True
        print("🆕 v69: historische RadioBox-titels genegeerd; start bij de nieuwste radio-uitzendingen.")
    failed = cache.setdefault("__v47_failed_tracks", {})
    known_queue = {_v47_key(x.get("artist", ""), x.get("title", ""))
                   for x in live_queue if isinstance(x, dict)}
    newly_queued = 0
    for source in radio_sources:
        sid = source["id"]
        source_seen = set(discovered.get(sid, []))
        to_prepend = []
        scanned = 0
        # v93: ALLE zichtbare radioplays inlezen, niet slechts twaalf.
        visible_tracks = source["tracks"]
        for artist, title in visible_tracks:
            artist, title = artist.strip(), title.strip()
            if not artist or not title:
                continue
            key = _v47_key(artist, title)
            if is_interview_fragment(title):
                source_seen.add(key)
                continue
            if key in source_seen:
                continue
            scanned += 1
            source_seen.add(key)
            if key in seen or key in known_queue:
                continue
            cached_failed = cache.get(f"__not_found_v{matching_version}__" + key)
            if cached_failed is not None:
                # Ook historische missers uit v46 blijven terugkomen.
                failed.setdefault(key, {"artist": artist, "title": title, "source": sid,
                                        "failed_at": cached_failed})
                continue
            to_prepend.append({"artist": artist, "title": title, "source": sid})
            known_queue.add(key)
        # v95: RadioBox levert nieuwste eerst; zet ontdekte nummers
        # chronologisch (oudste eerst) ACHTERAAN in de blijvende queue.
        live_queue.extend(reversed(to_prepend))
        newly_queued += len(to_prepend)
        discovered[sid] = sorted(source_seen)
        print(f"📚 {source['name']}: {scanned} nog niet eerder gescande titels; "
              f"{len(to_prepend)} toegevoegd aan wachtrij (hele zichtbare historiek).")
    return newly_queued


# v96: Detecteer nieuwe uitzendingen via de VORIGE RadioBox-meting,
# niet via het levenslange ontdekkingsgeheugen van v47.
def v96_collect_live_plays(radio_sources, cache, seen, live_queue,
                           matching_version=35):
    snapshots = cache.setdefault("__v96_radio_snapshots", {})
    playlist_keys = set(cache.get("__playlist_keys", []))
    known_queue = {_v47_key(x.get("artist", ""), x.get("title", ""))
                   for x in live_queue if isinstance(x, dict)}
    discovered = cache.setdefault("__v47_radio_discovered", {})
    added = 0
    for source in radio_sources:
        sid = source["id"]
        tracks = [(str(v110_correct_radio_artist(a, sid)).strip(), str(t).strip())
                  for a, t in source.get("tracks", []) if a and t]
        if not tracks:
            print(f"⏳ v96 {source['name']}: lege bronmeting; vorige stand behouden.")
            continue
        current = [(_v47_key(a, t), a, t) for a, t in tracks]
        old = snapshots.get(sid)
        if not isinstance(old, list):
            if sid in ("radio_x_chilled", "indie_select", "championship_vinyl", "dark_edge",
                       "dreampop_radio", "radio_indie_alternative", "dkfm_edge", "dkfm_shoegaze", "dkfm_classic"):
                # Nieuwe bronnen: eerste meting is uitsluitend een nulmeting.
                arrivals = []
                print(f"🕒 v96 {source['name']}: nulmeting; geen oude uitzendingen ingehaald.")
            else:
                # Bestaande bronnen: oorspronkelijk v98.1-gedrag behouden.
                arrivals = current[:12]
                print(f"🕒 v96 {source['name']}: recente 12 nummers bij start nagekeken.")
        else:
            previous = set(old)
            # De eerste gemeenschappelijke titel is de grens tussen de vorige
            # en de nieuwe meting; niets van vóór die grens inhalen.
            boundary = next((i for i, (key, _, _) in enumerate(current)
                             if key in previous), None)
            if boundary is None:
                # Tijdelijke radiogeschiedeniswissel: vermijd massale backfill.
                arrivals = current[:12]
                print(f"⚠️ v96 {source['name']}: geen overlap; maximaal 12 recente titels nagekeken.")
            else:
                arrivals = current[:boundary]
        # v114: verklaar elke nieuwe uitzending en controleer FIFO-append.
        accepted = 0
        queue_length_before = len(live_queue)
        queue_prefix_before = list(live_queue)
        reasons = {}
        seen_this_scan = set()
        for key, artist, title in reversed(arrivals):
            if key in seen_this_scan:
                reason = "herhaling binnen deze bronmeting"
            else:
                seen_this_scan.add(key)
                if is_confirmed_german_vocal(artist, title):
                    reason = "bevestigde Duitse zang"
                elif is_interview_fragment(title):
                    reason = "interviewfragment"
                elif key in known_queue:
                    reason = "staat al in live queue"
                elif key in seen:
                    reason = "al eerder verwerkt (seen-geheugen)"
                elif key in playlist_keys or radio_matches_playlist(artist, title, playlist_keys):
                    reason = "staat al in Spotify-playlist (cache)"
                elif cache.get(f"__not_found_v{matching_version}__" + key) is not None:
                    reason = "bestaande niet-gevondenregistratie"
                else:
                    live_queue.append({"artist": artist, "title": title, "source": sid})
                    known_queue.add(key)
                    accepted += 1
                    reason = f"ACHTERAAN toegevoegd (positie {len(live_queue)})"
            reasons[reason] = reasons.get(reason, 0) + 1
            print(f"🔍 v114 {source['name']}: {artist} — {title} → {reason}")
        # Append mag nooit bestaande queue-items verplaatsen of verwijderen.
        if (len(live_queue) != queue_length_before + accepted
                or live_queue[:queue_length_before] != queue_prefix_before):
            raise RuntimeError(f"v114 FIFO-integriteitscontrole mislukt: {sid}")
        if arrivals:
            print(f"🧾 v114 {source['name']}: " + "; ".join(
                f"{reason}={count}" for reason, count in reasons.items()))
        print(f"📥 v114 {source['name']}: bestaande {queue_length_before} queue-items "
              f"behouden; {accepted} achteraan toegevoegd; nu {len(live_queue)}.")
        added += accepted
        discovered[sid] = sorted(set(discovered.get(sid, [])) | {k for k, _, _ in current})
        snapshots[sid] = [k for k, _, _ in current[:100]]
        print(f"📚 v96 {source['name']}: {len(arrivals)} recente uitzending(en) sinds vorige meting; "
              f"{accepted} toegevoegd aan live queue.")
    return added


# v50: Duyster-missers verdwijnen na de volledige set zoekstrategieën
# uit de shuffle. Bewaar ze afzonderlijk zodat we ze bij een latere
# algemene matcherverbetering gecontroleerd opnieuw kunnen beoordelen.
def v50_archive_duyster_miss(cache, artist, title, now=None):
    now = time.time() if now is None else now
    key = _v47_key(artist, title)
    cache.setdefault("__v50_duyster_unmatched", {}).setdefault(key, {
        "artist": artist, "title": title, "failed_at": int(now),
        "matching_version": 34,
    })
    cache.setdefault("__v47_failed_tracks", {}).pop(key, None)
    return key


def v50_clean_duyster_retries(cache, live_queue):
    """Migrate old exhausted Duyster retries and remove their queued copies."""
    blocked = cache.setdefault("__v50_duyster_unmatched", {})
    failed = cache.setdefault("__v47_failed_tracks", {})
    newly_blocked = 0
    for key, entry in list(failed.items()):
        if not isinstance(entry, dict) or entry.get("source") != "duyster":
            continue
        if key not in blocked:
            v50_archive_duyster_miss(cache, entry.get("artist", ""),
                                    entry.get("title", ""), entry.get("failed_at"))
            newly_blocked += 1
        failed.pop(key, None)
    before = len(live_queue)
    live_queue[:] = [item for item in live_queue if not (
        isinstance(item, dict) and item.get("source") == "duyster" and
        _v47_key(item.get("artist", ""), item.get("title", "")) in blocked
    )]
    return newly_blocked, before - len(live_queue)


# Geef nieuwe Duyster-archiefnummers voorrang op oude, mislukte matches.
# Het historisch archief zelf blijft volledig onaangeraakt.
DUYSTER_OLD_MISS_RECHECK_INTERVAL = 6 * 3600


def v51_revisit_archived(cache, seen, live_queue, matching_version=35, batch=1):
    """Herbekijk oude Duyster-missers zonder de gewone shuffle te verdringen.

    Per oude misser maximaal één herstelreeks in deze matcher-versie.
    Hoogstens één nieuwe oude-misser-hercontrole per zes uur. De laatst
    ingeplande tijd wordt in de bestaande persistente cache bewaard.
    """
    now = int(time.time())
    last = cache.get("__duyster_old_miss_last_recheck_at", 0)
    try:
        last = int(last)
    except (ValueError, TypeError):
        last = 0
    if last > now or (last and now - last < DUYSTER_OLD_MISS_RECHECK_INTERVAL):
        return 0

    archive = cache.setdefault("__v50_duyster_unmatched", {})
    inspected = cache.setdefault("__v51_archived_inspected", [])
    inspected_keys = set(inspected)
    active = {_v47_key(x.get('artist',''), x.get('title',''))
              for x in live_queue if isinstance(x,dict)}
    # Hoogstens één oude hercontrole tegelijk, naast de gewone Duyster-shuffle.
    already_rechecking = sum(bool(isinstance(x,dict) and x.get('_v51_archive_recheck')) for x in live_queue)
    if already_rechecking >= 1:
        return 0
    batch = min(batch, 1)
    issued = 0
    for key, entry in list(archive.items()):
        if issued >= batch:
            break
        if key in inspected_keys or key in active or key in seen:
            continue
        if not isinstance(entry,dict) or is_interview_fragment(entry.get('title','')):
            inspected.append(key)
            continue
        artist, title = entry.get('artist',''), entry.get('title','')
        if not artist or not title:
            inspected.append(key)
            continue
        inspected.append(key)  # vóór zoeken persistente markering
        archive.pop(key,None)  # Duyster mag opnieuw één keer zoeken
        cache.pop(f'__not_found_v{matching_version}__'+key,None)
        live_queue.append({'artist':artist,'title':title,'source':'duyster',
                           '_v51_archive_recheck': True, '_v34_search_variant': 0})
        issued += 1
        cache["__duyster_old_miss_last_recheck_at"] = now
    return issued


RADIO_FAILED_SEARCH_LIMIT = 5


def v51_radio_failure_key(artist, title):
    return _v47_key(artist, title)


def v51_radio_failed_count(cache, artist, title):
    return int(cache.get('__v51_radio_failed_searches', {}).get(
        v51_radio_failure_key(artist, title), 0) or 0)


def v51_radio_park(cache, artist, title, source, attempts):
    key = v51_radio_failure_key(artist, title)
    cache.setdefault('__v51_radio_unmatched', {})[key] = {
        'artist': artist, 'title': title, 'source': source,
        'failed_at': int(time.time()), 'matching_version': 35,
        'failed_searches': attempts,
    }
    cache.setdefault('__v47_failed_tracks', {}).pop(key, None)


def v51_release_old_radio_failures(cache, limit=1):
    """Gefaseerde herstelronde voor radio-missers van vóór matcher v51.

    Verlaagt alleen hun wachttijd; de bestaande v47-retryfunctie bewaakt
    queue-duplicaten en bronverdeling. Geen nieuwe Spotify Search op zich.
    """
    failed = cache.setdefault('__v47_failed_tracks', {})
    if '__v51_radio_release_pending' not in cache:
        cache['__v51_radio_release_pending'] = [
            key for key, entry in failed.items()
            if isinstance(entry,dict) and entry.get('source') in ('vuurland','mellow_mix','big_sonic_heaven')
        ]
    pending = cache['__v51_radio_release_pending']
    released = 0
    while pending and released < limit:
        key = pending.pop(0)
        if key not in failed:
            continue
        if key in cache.get('__v51_radio_unmatched', {}):
            continue
        # Een oude misser met vijf geregistreerde mislukte searches niet vrijgeven.
        if int(cache.get('__v51_radio_failed_searches', {}).get(key, 0) or 0) >= RADIO_FAILED_SEARCH_LIMIT:
            entry = failed.get(key, {})
            v51_radio_park(cache, entry.get('artist', ''), entry.get('title', ''),
                           entry.get('source', 'vuurland'), RADIO_FAILED_SEARCH_LIMIT)
            continue
        failed[key]['failed_at'] = 0
        cache.pop('__not_found_v35__'+key,None)
        cache.pop('__not_found_v34__'+key,None)
        released += 1
    return released


def v47_restore_retries(cache, seen, live_queue, now=None, cooldown=86400, max_per_run=4):
    """Restore failed songs after their cooldown, no perpetual silent loss."""
    now = time.time() if now is None else now
    failed = cache.setdefault("__v47_failed_tracks", {})
    known = {_v47_key(x.get("artist", ""), x.get("title", ""))
             for x in live_queue if isinstance(x, dict)}
    count = 0
    for key, entry in list(failed.items()):
        if isinstance(entry, dict) and entry.get("source") == "duyster":
            v50_archive_duyster_miss(cache, entry.get("artist", ""),
                                    entry.get("title", ""), entry.get("failed_at"))
            failed.pop(key, None)
            continue
        if is_interview_fragment(entry.get("title", "")):
            del failed[key]
            continue
        if key in cache.get('__v51_radio_unmatched', {}):
            del failed[key]
            continue
        if key in seen:
            del failed[key]
            continue
        if key in known:
            del failed[key]
            continue
        try:
            last_failed = float(entry.get("failed_at", 0))
        except (TypeError, ValueError):
            last_failed = now
        if now < last_failed + cooldown or count >= max_per_run:
            continue
        live_queue.append({"artist": entry["artist"], "title": entry["title"],
                           "source": entry.get("source", "duyster")})
        known.add(key)
        del failed[key]
        count += 1
    return count


def v47_remember_failed(cache, artist, title, source, now=None):
    if is_interview_fragment(title):
        return
    if source == "duyster":
        v50_archive_duyster_miss(cache, artist, title, now)
        return
    now = time.time() if now is None else now
    key = _v47_key(artist, title)
    if v51_radio_failed_count(cache, artist, title) >= RADIO_FAILED_SEARCH_LIMIT:
        v51_radio_park(cache, artist, title, source,
                       v51_radio_failed_count(cache, artist, title))
        return
    # Niet elke dag dezelfde radio-misser opnieuw: twee VOLLEDIGE reeksen
    # van drie zoekstrategieën, daarna in controleerbaar archief parkeren.
    cycles = cache.setdefault('__v51_radio_failed_cycles', {})
    cycle_count = int(cycles.get(key,0)) + 1
    cycles[key] = cycle_count
    if cycle_count >= 2:
        cache.setdefault('__v51_radio_unmatched', {})[key] = {
            'artist': artist, 'title': title, 'source': source,
            'failed_at': int(now), 'matching_version': 35,
            'full_search_cycles': cycle_count,
        }
        cache.setdefault('__v47_failed_tracks', {}).pop(key,None)
        return
    cache.setdefault("__v47_failed_tracks", {})[key] = {
        "artist": artist, "title": title, "source": source, "failed_at": int(now)}

def load_duyster_confirmed_links(csv_path):
    """Read-only. Only exact archive identities from the audited strict proposal CSV.

    Ambiguous identities are excluded rather than arbitrarily picking a recording.
    The file must be deployed explicitly next to vuurland_sync.py.
    """
    import pathlib
    path = pathlib.Path(csv_path)
    if not path.is_file():
        print('ℹ️ Duyster-koppeltabel ontbreekt: normale matcher blijft actief.')
        return {}
    links, ambiguous = {}, set()
    try:
        with path.open('r', newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                if row.get('controle_status') != 'strikt_koppelvoorstel':
                    continue
                if str(row.get('is_playable_api', '')).lower() != 'true':
                    continue
                tid = str(row.get('spotify_track_id') or '').strip()
                isrc = str(row.get('isrc') or '').strip().upper()
                if not re.fullmatch(r'[a-zA-Z0-9]{22}', tid):
                    continue
                if not re.fullmatch(r'[a-zA-Z0-9]{12}', isrc):
                    continue
                if str(row.get('spotify_url') or '').strip() != 'https://open.spotify.com/track/' + tid:
                    continue
                artist, title = str(row.get('artist') or ''), str(row.get('title') or '')
                if (normalize_match(artist) != normalize_match(row.get('spotify_artiest')) or
                        normalize_match(title) != normalize_match(row.get('spotify_titel'))):
                    continue
                key = f'{normalize_match(artist)}|||{normalize_match(title)}'
                proposed = ('spotify:track:' + tid, isrc)
                if key in links and links[key] != proposed:
                    ambiguous.add(key)
                else:
                    links[key] = proposed
    except (OSError, UnicodeError, csv.Error) as error:
        print(f'⚠️ Duyster-koppeltabel onleesbaar ({error}); normale matcher blijft actief.')
        return {}
    for key in ambiguous:
        links.pop(key, None)
    print(f'🔗 Duyster: {len(links)} gecontroleerde archiefkoppelingen geladen; '
          f'{len(ambiguous)} conflicten geweerd. Geen Spotify Search.')
    return links


# v78: eenmalige inhaalprioriteit voor gecontroleerde v77-matcherherstellingen.
# Geen directe Spotify-toevoegingen: alle gewone playlist-, duplicaat-,
# afspeelbaarheids- en API-controles blijven actief.
V78_RECOVERY_TRACKS = (
    ("BON IVER", "Speyside"),
    ("Don Williams", "'Till The Rivers Run Dry"),
    ("Prince", "affirmations Way Back Home"),
    ("The Gabby Pahinui Hawaiian Band", "Wahine uʻi"),
    ("NOVASTAR & PIET GODDAER", "Never back down"),
)


def v78_recover_and_prioritize(cache, live_queue, radio_sources):
    """Herstel alleen aantoonbaar bestaande radiosongs; houd hun volgorde vast.

    Bron moet blijken uit radiohistoriek of bewaarde state, nooit gegokt.
    De migratie loopt slechts eenmaal; opnieuw starten dupliceert niets.
    """
    target_keys = [_v47_key(a, t) for a, t in V78_RECOVERY_TRACKS]
    if not cache.get('__v78_recovery_initialized'):
        source_for = {}
        for source in radio_sources:
            for artist, title in source.get('tracks', []):
                source_for.setdefault(_v47_key(artist, title), source['id'])
        for store_name in ('__v47_failed_tracks', '__v51_radio_unmatched'):
            for key, entry in cache.get(store_name, {}).items():
                if isinstance(entry, dict) and entry.get('source') in ('vuurland', 'mellow_mix', 'big_sonic_heaven'):
                    source_for.setdefault(key, entry['source'])
        for item in live_queue:
            if isinstance(item, dict) and item.get('source') in ('vuurland', 'mellow_mix', 'big_sonic_heaven'):
                source_for.setdefault(_v47_key(item.get('artist',''), item.get('title','')), item['source'])
        existing = {_v47_key(x.get('artist',''), x.get('title',''))
                    for x in live_queue if isinstance(x, dict)}
        restored = 0
        for artist, title in V78_RECOVERY_TRACKS:
            key = _v47_key(artist, title)
            if key not in source_for:
                print(f'ℹ️ v78: bron niet bevestigd; geen kunstmatige queue-entry: {artist} — {title}')
                continue
            cache.setdefault('__v47_failed_tracks', {}).pop(key, None)
            cache.setdefault('__v51_radio_unmatched', {}).pop(key, None)
            cache.setdefault('__v51_radio_failed_searches', {}).pop(key, None)
            cache.setdefault('__v51_radio_failed_cycles', {}).pop(key, None)
            for prefix in ('__not_found_v35__', '__match_v35__'):
                cache.pop(prefix + key, None)
            if key not in existing:
                live_queue.append({'artist': artist, 'title': title,
                                   'source': source_for[key], '_v34_search_variant': 0})
                existing.add(key)
                restored += 1
            for item in live_queue:
                if isinstance(item, dict) and _v47_key(item.get('artist',''), item.get('title','')) == key:
                    item.pop('_v34_retry_at', None)
                    item['_v34_search_variant'] = 0
        cache['__v78_recovery_initialized'] = True
        print(f'🎯 v78: {restored} geparkeerde matcher-items hersteld; prioriteit alleen voor bestaande radiobronnen.')
    active = {_v47_key(x.get('artist',''), x.get('title',''))
              for x in live_queue if isinstance(x, dict)}
    return {key: pos for pos, key in enumerate(target_keys) if key in active}


# v81: eenmalige veilige herkansing zodra de cataloguslocator beschikbaar is.
# Alleen een eerder werkelijk gezien radioliedje; geen nieuwe bron verzinnen.
def v81_requeue_confirmed_catalog(cache, live_queue, radio_sources):
    if cache.get('__v81_catalog_retry_initialized'):
        return 0
    sources = {}
    for source in radio_sources:
        for artist, title in source.get('tracks', []):
            key = _v47_key(artist, title)
            sources.setdefault(key, source['id'])
    for store_name in ('__v47_failed_tracks', '__v51_radio_unmatched'):
        for key, entry in cache.get(store_name, {}).items():
            if isinstance(entry, dict) and entry.get('source') in ('vuurland','mellow_mix','big_sonic_heaven'):
                sources.setdefault(key, entry['source'])
    active = {_v47_key(x.get('artist',''), x.get('title','')) for x in live_queue
              if isinstance(x, dict)}
    released = 0
    for (artist, title), locator in V81_VERIFIED_CATALOG_TRACKS.items():
        key = _v47_key(artist, title)
        source = sources.get(key)
        if not source:
            print(f'ℹ️ v81: radiobron niet bevestigd; geen nieuwe queue-entry: {artist} — {title}')
            continue
        cache.get('__v47_failed_tracks', {}).pop(key, None)
        cache.get('__v51_radio_unmatched', {}).pop(key, None)
        cache.get('__v51_radio_failed_searches', {}).pop(key, None)
        cache.get('__v51_radio_failed_cycles', {}).pop(key, None)
        for name in list(cache):
            if name.startswith('__not_found_v') and name.endswith(key):
                cache.pop(name, None)
        if key not in active:
            live_queue.insert(0, {'artist':artist, 'title':title, 'source':source,
                                  '_v34_search_variant':0})
            active.add(key)
            released += 1
        for item in live_queue:
            if isinstance(item, dict) and _v47_key(item.get('artist',''),item.get('title','')) == key:
                item.pop('_v34_retry_at', None)
                item['_v34_search_variant'] = 0
    cache['__v81_catalog_retry_initialized'] = True
    print(f'📀 v81: {released} bevestigd(e) catalogusnummer(s) opnieuw ingepland.')
    return released


# v83: wis uitsluitend foutregistraties nadat een nummer aantoonbaar is
# verwerkt (gevonden, al aanwezig of als duplicaat geweigerd).
# Geen bulkopschoning van oude mislukkingen; geen Spotify-verzoeken.
def v83_clear_resolved_failures(cache, artist, title):
    key = _v47_key(artist, title)
    removed = 0
    for name in (
        '__v47_failed_tracks',
        '__v51_radio_unmatched',
        '__v51_radio_failed_searches',
        '__v51_radio_failed_cycles',
    ):
        store = cache.get(name)
        if isinstance(store, dict) and key in store:
            del store[key]
            removed += 1
    for name in list(cache):
        if name.startswith('__not_found_v') and name.endswith('__' + key):
            cache.pop(name, None)
            removed += 1
    if removed:
        print(f"🧹 v83: {removed} oude foutregistratie(s) opgelost: {artist} — {title}")
    return removed


# v116: stabiele FIFO-volgorde per bron, ook na retries.
# De bestaande queue wordt bij de eerste run éénmalig in zijn huidige volgorde
# genummerd. Daarna krijgen ALLEEN nieuwe items een hoger volgnummer.
# Niets wissen, hersorteren of uit de queue verplaatsen.
def v116_stamp_fifo(live_queue, cache):
    raw = cache.get("__v116_fifo_next_sequence", 1)
    try:
        next_seq = max(1, int(raw))
    except (TypeError, ValueError, OverflowError):
        next_seq = 1
    used = set()
    # Ook na een oudere state-restore nooit bestaande nummers hergebruiken.
    for item in live_queue:
        if not isinstance(item, dict):
            continue
        seq = item.get("_v116_fifo_seq")
        if type(seq) is int and seq > 0 and seq not in used:
            used.add(seq)
            next_seq = max(next_seq, seq + 1)
    stamped = 0
    seen_here = set()
    for item in live_queue:
        if not isinstance(item, dict):
            continue
        seq = item.get("_v116_fifo_seq")
        if type(seq) is int and seq > 0 and seq not in seen_here:
            seen_here.add(seq)
            continue
        while next_seq in used:
            next_seq += 1
        item["_v116_fifo_seq"] = next_seq
        used.add(next_seq)
        seen_here.add(next_seq)
        next_seq += 1
        stamped += 1
    cache["__v116_fifo_next_sequence"] = next_seq
    return stamped



# v131: expliciete gebruikersvoorkeur; alleen CJK-schrift herkennen, geen taalgok.
def v131_block_nonlatin_east_asian(artist, title):
    # Han (Chinese karakters / Kanji), Hiragana, Katakana, Hangul, Bopomofo.
    # Andere alfabetten en Latijnse letters met accenten blijven behouden.
    for character in str(artist or "") + str(title or ""):
        cp = ord(character)
        if (0x3400 <= cp <= 0x9FFF or
            0xF900 <= cp <= 0xFAFF or
            0x20000 <= cp <= 0x3134F or
            0x3040 <= cp <= 0x30FF or
            0x31F0 <= cp <= 0x31FF or
            0xFF66 <= cp <= 0xFF9F or
            0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
            0x3130 <= cp <= 0x318F or
            0xA960 <= cp <= 0xA97F or
            0xD7B0 <= cp <= 0xD7FF or
            0x3100 <= cp <= 0x312F or
            0x31A0 <= cp <= 0x31BF):
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
        {
            "id": "big_sonic_heaven",
            "name": "Big Sonic Heaven Radio",
            "tracks": get_big_sonic_heaven_tracks(),
            "cache_key": "__last_radio_key_big_sonic_heaven",
        },
        {
            "id": "radio_x_chilled",
            "name": "Radio X Chilled",
            "tracks": get_radio_x_chilled_tracks(),
            "cache_key": "__last_radio_key_radio_x_chilled",
        },
        {
            "id": "indie_select",
            "name": "Indie Select",
            "tracks": get_indie_select_tracks(),
            "cache_key": "__last_radio_key_indie_select",
        },
        {
            "id": "championship_vinyl",
            "name": "Championship Vinyl",
            "tracks": get_championship_vinyl_tracks(),
            "cache_key": "__last_radio_key_championship_vinyl",
        },
        {
            "id": "dark_edge",
            "name": "Dark Edge Radio",
            "tracks": get_dark_edge_tracks(),
            "cache_key": "__last_radio_key_dark_edge",
        },
        {
            "id": "dreampop_radio",
            "name": "Dreampop Radio",
            "tracks": get_dreampop_radio_tracks(),
            "cache_key": "__last_radio_key_dreampop_radio",
        },
        {
            "id": "radio_indie_alternative",
            "name": "Radio Indie Alternative",
            "tracks": get_radio_indie_alternative_tracks(),
            "cache_key": "__last_radio_key_radio_indie_alternative",
        },
        {
            "id": "dkfm_edge",
            "name": "DKFM Edge",
            "tracks": get_dkfm_edge_tracks(),
            "cache_key": "__last_radio_key_dkfm_edge",
        },
        {
            "id": "dkfm_shoegaze",
            "name": "DKFM Shoegaze Radio",
            "tracks": get_dkfm_shoegaze_tracks(),
            "cache_key": "__last_radio_key_dkfm_shoegaze",
        },
        {
            "id": "dkfm_classic",
            "name": "DKFM Classic",
            "tracks": get_dkfm_classic_tracks(),
            "cache_key": "__last_radio_key_dkfm_classic",
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
    # Persistente wachtrij, inclusief eerder opgebouwde radio-achterstand.
    # Geen bestaande nummers wissen bij een code-update.
    # ---------------------------------

    live_queue_file = os.path.join(
        DATA_DIR,
        "vuurland_live_queue.json"
    )

    try:
        with open(live_queue_file, "r") as f:
            live_queue = json.load(f)
    except FileNotFoundError:
        live_queue = []

    if not isinstance(live_queue, list):
        raise ValueError("Live queue is geen JSON-lijst; niet overschrijven")

    # v48: interviews uit reeds bestaande wachtrij filteren vóór de scheduler.
    interviews_in_queue = sum(
        isinstance(x, dict) and is_interview_fragment(x.get("title", ""))
        for x in live_queue
    )
    if interviews_in_queue:
        live_queue = [x for x in live_queue if not (
            isinstance(x, dict) and is_interview_fragment(x.get("title", ""))
        )]
        print(f"⏭️ {interviews_in_queue} interviewfragment(en) uit wachtrij gehaald zonder Spotify Search.")

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

    MATCHING_RULES_VERSION = 35
    if cache.get(
        "__matching_rules_version"
    ) != MATCHING_RULES_VERSION:

        bad_positive_cache_keys = {
            "sufjan stevens|||love yourself",
            "pinback|||loro",
            "ise|||ik reis door de nacht (live)",
            "the flaming lips|||do you realise",
            "taylor swift feat bon iver|||exile",
            "the beatles|||dear prudence",
            "led zeppelin|||the rain song",
            "santana|||flor d'luna (moonflower)",
            "robert plant|||song to the siren",
            "sasami & angie mcmahon|||honeycrash",
            "sam fender & holly humberstone|||seventeen going under",
            "doc watson & david grisman|||summertime",
            "sam roberts|||hard road",
            "liz cooper & the stampede|||the night",
            "lyle lovett|||friend of the devil",
            "robert plant|||killing the blues",
            "kids with buns|||nothing",
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

    # v49: twee door de gebruiker exact gelinkte Spotify-tracks hoeven
    # niet langer een oude 24-uurs 'niet gevonden'-cooldown af te wachten.
    # Houd bestaande geschiedenis, seen, queue en andere cache-items intact.
    if not cache.get("__v49_confirmed_links_released"):
        for exact_artist, exact_title in (
            ("father john misty", "to r."),
            ("iso68", "est plus"),
        ):
            exact_key = _v47_key(exact_artist, exact_title)
            cache.pop(f"__not_found_v{MATCHING_RULES_VERSION}__" + exact_key, None)
            cache.pop(f"__match_v{MATCHING_RULES_VERSION}__" + exact_key, None)
            failed_item = cache.get("__v47_failed_tracks", {}).get(exact_key)
            if isinstance(failed_item, dict):
                failed_item["failed_at"] = 0
            for queued_item in live_queue:
                if isinstance(queued_item, dict) and _v47_key(
                    queued_item.get("artist", ""), queued_item.get("title", "")
                ) == exact_key:
                    queued_item.pop("_v34_retry_at", None)
                    queued_item["_v34_search_variant"] = 0
        cache["__v49_confirmed_links_released"] = True
        print("🎯 v49: bevestigde Spotify-links voor To R. en Est Plus vrijgegeven.")

    # v71: alleen de zes door de gebruiker nagekeken afwijzingen éénmalig
    # opnieuw proberen. Neem de ECHTE bron uit de bestaande cache over;
    # maak geen radio-uitzending of artiest-/titelvariant uit het niets.
    if not cache.get('__v71_six_matcher_retries_released'):
        reviewed = {
            (normalize_match(a), normalize_match(t))
            for a, t in (
                ('THE ANXIETY (WILLOW & TYLER COLE)', 'Meet me at our spot'),
                ('Meshell Ndegeocello', 'Don’t You Want Me (with Cat Power)'),
                ('ESKOBAR & HEATHER NOVA', 'Someone'),
                ('Mark Knopfler and Emmylou Harris', 'Beachcombing'),
                ('Vince Guaraldi', 'Charlie Brown Theme'),
                ('Eurythmics', 'Here Comes the Rain Again (acoustic)'),
            )
        }
        active = {_v47_key(x.get('artist',''), x.get('title',''))
                  for x in live_queue if isinstance(x,dict)}
        released = 0
        old_failed = cache.setdefault('__v47_failed_tracks', {})
        parked = cache.setdefault('__v51_radio_unmatched', {})
        all_keys = set(old_failed) | set(parked)
        for key in sorted(all_keys):
            entry = parked.get(key) or old_failed.get(key)
            if not isinstance(entry, dict):
                continue
            artist, title = entry.get('artist',''), entry.get('title','')
            if (normalize_match(artist), normalize_match(title)) not in reviewed:
                continue
            source = entry.get('source')
            if source not in ('vuurland', 'mellow_mix', 'big_sonic_heaven'):
                continue
            old_failed.pop(key,None)
            parked.pop(key,None)
            cache.get('__v51_radio_failed_searches', {}).pop(key,None)
            cache.get('__v51_radio_failed_cycles', {}).pop(key,None)
            cache.pop(f'__not_found_v{MATCHING_RULES_VERSION}__'+key,None)
            cache.pop(f'__match_v{MATCHING_RULES_VERSION}__'+key,None)
            if key not in active:
                live_queue.append({'artist':artist, 'title':title, 'source':source,
                                   '_v34_search_variant':0})
                active.add(key)
            released += 1
        for item in live_queue:
            if not isinstance(item, dict):
                continue
            if (normalize_match(item.get('artist','')),
                normalize_match(item.get('title',''))) in reviewed:
                item.pop('_v34_retry_at',None)
                item['_v34_search_variant']=0
        cache['__v71_six_matcher_retries_released'] = True
        if released:
            print(f'♻️ v71: {released} eerder geparkeerde nummers opnieuw ingepland.')

    # v95: eenmalige overgang naar uitsluitend uitzendingen VANAF de omschakeling.
    # Bewaar de oude wachtrij als archief in de bestaande cache: geen verlies
    # van informatie, maar geen historische Spotify-zoekopdrachten meer.
    # Vereis drie geslaagde RadioBox-metingen voordat de nulmeting plaatsvindt.
    if not cache.get("__v95_live_fifo_initialized"):
        if any(not src.get("tracks") for src in radio_sources
               if src["id"] in RADIO_SOURCE_ORDER[:3]):
            print("⏳ v95: wacht op drie volledige bronmetingen vóór live-start; "
                  "bestaande wachtrij blijft bewaard.")
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            return
        archived = cache.setdefault("__v95_archived_pre_live_queue", [])
        archived.extend(x for x in live_queue if isinstance(x, dict))
        removed = len(live_queue)
        live_queue.clear()
        discovered = cache.setdefault("__v47_radio_discovered", {})
        for src in radio_sources:
            previous = set(discovered.get(src["id"], []))
            previous.update(_v47_key(a, t) for a, t in src["tracks"] if a and t)
            discovered[src["id"]] = sorted(previous)
        # Oude mislukte matches blijven in het archief, niet actief als retries.
        old_failed = cache.get("__v47_failed_tracks", {})
        if isinstance(old_failed, dict):
            cache["__v95_archived_pre_live_failures"] = dict(old_failed)
            cache["__v47_failed_tracks"] = {}
        cache["__v95_live_fifo_initialized"] = True
        # Behoud de beurtrolcursor van de bestaande state.
        atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
        save_cache(cache)
        print(f"🕒 v95: live-start vanaf huidige RadioBox-meting; "
              f"{removed} oude wachtitems veilig gearchiveerd, niet meer actief.")

    # Geen historische herstel-injecties in de nieuwe live FIFO.
    # De bestaande matcher- en playlist-cache blijven behouden.

    queued_keys = {
        f"{normalize_match(item.get('artist', ''))}|||"
        f"{normalize_match(item.get('title', ''))}"
        for item in live_queue
        if isinstance(item, dict)
    }

    # v47: registreer ALLE zichtbare RadioBox-titels; niet alleen de
    # nummers vóór de vorige cursor. Dit gebruikt geen Spotify Search.
    for source in radio_sources:
        if source["tracks"]:
            artist, title = source["tracks"][0]
            cache[source["cache_key"]] = _v47_key(artist, title)

    added_to_live_queue = v96_collect_live_plays(
        radio_sources, cache, seen, live_queue, MATCHING_RULES_VERSION)
    if added_to_live_queue:
        print(f"🆕 {added_to_live_queue} beschikbare RadioBox-titels in wachtrij.")
    else:
        print("ℹ️ Geen nieuwe, nog niet gescande RadioBox-titels.")

    _v116_new = v116_stamp_fifo(live_queue, cache)
    if _v116_new:
        print(f"📥 v116: {_v116_new} queue-item(s) een vaste FIFO-positie gegeven.")

    # v67: blijf RadioBox volgen tijdens de Spotify-cooldown. De ingestie
    # hierboven gebruikt geen Spotify API; verdere matcher-/playliststappen
    # zouden dat wel kunnen doen. Daarom hier bewust vroeg terugkeren.
    blocked_until = float(cache.get("__spotify_api_blocked_until", 0) or 0)
    server_until = float(cache.get("__spotify_server_error_until", 0) or 0)
    if max(blocked_until, server_until) > time.time():
        atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
        save_cache(cache)
        pause_until = max(blocked_until, server_until)
        kind = "Spotify 429-cooldown" if blocked_until >= server_until else "tijdelijke Spotify-serverpauze"
        print(f"⏸️ v70 RADIO-ONLY ({kind}) tot "
              f"{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(pause_until))}.")
        print(f"📻 Nieuwe RadioBox-titels veilig bewaard; "
              f"{len(live_queue)} nummers in wachtrij; 0 Spotify-verzoeken.")
        return

    blocked_now, removed_from_queue = (0, 0)
    if blocked_now or removed_from_queue:
        print(f"🧹 v50: {blocked_now} oude Duyster-missers uitgesloten; "
              f"{removed_from_queue} herhaalde wachtrij-items verwijderd.")
    rechecks = 0  # v54: geen ongefilterde Duyster-revivals
    if rechecks:
        print(f"♻️ v51: {rechecks} vroegere Duyster-misser opnieuw ingepland met nieuwe matcher.")
    released_radio = 0  # v95: oude radio-fouten niet opnieuw activeren
    if released_radio:
        print(f'♻️ v51: {released_radio} radio-misser opnieuw beoordeeld na matcherupdate.')
    restored = v47_restore_retries(cache, seen, live_queue)
    if restored:
        print(f"🔁 {restored} eerdere onbetrouwbare match(es) opnieuw ingepland.")

    # v119: verwijder Duitse TITELS uit de bestaande wachtrij; geen Spotify-mutatie.
    # Duitse artiesten met niet-Duitse titels blijven behouden.
    # v131: bestaande en nieuw toegevoegde FIFO-items vóór Spotify opschonen.
    _v131_before = len(live_queue)
    live_queue = [x for x in live_queue if not (
        isinstance(x, dict) and v131_block_nonlatin_east_asian(
            x.get("artist", ""), x.get("title", "")))]
    if len(live_queue) != _v131_before:
        print(f"⏭️ v131: {_v131_before - len(live_queue)} CJK-titel(s)/artiest(en) uit FIFO geweerd.")
    _v119_before = len(live_queue)
    live_queue = [x for x in live_queue if isinstance(x, dict) and
                  x.get("source") in RADIO_SOURCE_ORDER and
                  not v119_is_german_title(x.get("title", "")) and
                  not is_confirmed_german_vocal(x.get("artist", ""), x.get("title", ""))]
    _v119_removed = _v119_before - len(live_queue)
    if _v119_removed:
        print(f"🧹 v119: {_v119_removed} Duitstalige titel(s)/bevestigde Duitse zang uit live queue verwijderd.")
    atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
    save_cache(cache)

    _v116_restored = v116_stamp_fifo(live_queue, cache)
    if _v116_restored:
        atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
        save_cache(cache)
        print(f"📥 v116: {_v116_restored} herstelde queue-item(s) achteraan genummerd.")

    # ---------------------------------
    # ALS ER GEEN NUMMER TE VERWERKEN IS
    # ---------------------------------

    if not live_queue:
        # v120: geen bronbeurtrol, ook niet wanneer de wachtrij leeg is.
        atomic_save_json(live_queue_file, [], indent=2, ensure_ascii=False)
        save_cache(cache)
        print("ℹ️ v120: gezamenlijke live queue is leeg.")
        return

    # ---------------------------------
    # PLAYLIST
    # ---------------------------------

    try:
        (
            playlist_id,
            active_volume_number,
            active_playlist_count,
        ) = get_active_volume_playlist(cache)

        if active_volume_number >= 1:
            _retry_one_pending_library_like(cache)

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

    global SPOTIFY_SEARCH_HTTP_USED
    SPOTIFY_SEARCH_HTTP_USED = 0
    searches_used = 0
    MAX_SEARCHES_PER_RUN = 1  # v66: één gedeelde Spotify Search per 120 seconden
    NOT_FOUND_COOLDOWN_SECONDS = 86400  # 24 uur

    v129_restore_volume_dedupe(cache, active_volume_number)
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

    # v69: detecteer ook handmatig uit Chill Mix toegevoegde nummers.
    # Eén keer per 24 uur, om Spotify API-verzoeken te beperken. Een lege nieuwe lijst is ook een geldige
    # cache en mag niet voortdurend opnieuw worden gescand.
    PLAYLIST_CACHE_SECONDS = 86400

    if (
        not playlist_isrc_cache_ready
        or time.time() - playlist_cache_time >= PLAYLIST_CACHE_SECONDS
    ):

        print(
            "📋 Spotify-playlist cache vernieuwen..."
        )

        if active_volume_number <= 1:
            playlist_keys = set()
            playlist_uris = set()
            playlist_isrcs = set()
        else:
            # Gesloten volumes blijven in de globale dedupe-cache.
            # Alleen het actieve volume wordt opnieuw gescand.
            playlist_keys = set(cache.get("__playlist_keys", []))
            playlist_uris = set(cache.get("__playlist_uris", []))
            playlist_isrcs = set(cache.get("__playlist_isrcs", []))

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
                    f"   mogelijk duplicaat: {entry['uri']}"
                )
                duplicate_uris_to_remove.append(
                    entry["uri"]
                )

        if duplicate_uris_to_remove:
            print(
                f"🛡️ v84: {len(set(duplicate_uris_to_remove))} "
                "mogelijke bestaande ISRC-duplicaten gevonden. "
                "Geen nummers verwijderd."
            )

        active_playlist_count = playlist_position

        cache[
            "__vuurland_active_playlist_count"
        ] = active_playlist_count

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

    duyster_confirmed_links = {}  # v69: Duyster volledig uitgeschakeld

    # v120: gezamenlijke FIFO zonder bronbeurtrol.
    # Alle twaalf RadioBox-bronnen blijven iedere ronde nieuwe titels achteraan
    # toevoegen. De bestaande persistente _v116_fifo_seq blijft leidend.
    processed_item_ids = set()
    max_queue_items_per_round = 35
    source_order = RADIO_SOURCE_ORDER
    print("🔀 v137: 12 bronnen samen, één FIFO, geen beurtrol.")
    additions_this_round = 0
    duyster_additions_this_round = 0
    max_additions_per_round = 1  # v66: maximaal één playlisttoevoeging en bijbehorende like

    # v41: één gedeelde cooldown-check voor planning én logging.
    # Een 24-uurs "niet gevonden"-item is NIET zoekklaar, ook wanneer
    # _v34_retry_at ontbreekt. We bewaren queue en cache volledig.
    def _v41_cooldown_until(candidate):
        retry_at = int(candidate.get("_v34_retry_at", 0) or 0)
        key = (f"{normalize_match(candidate.get('artist', ''))}|||"
               f"{normalize_match(candidate.get('title', ''))}")
        not_found = cache.get(f"__not_found_v{MATCHING_RULES_VERSION}__" + key)
        if not_found is None:
            return retry_at
        try:
            not_found_until = int(float(not_found)) + NOT_FOUND_COOLDOWN_SECONDS
        except (ValueError, TypeError, OverflowError):
            not_found_until = 0
        return max(retry_at, not_found_until)

    _radio_ready = 0
    _radio_short_cooldown = 0
    _radio_not_found_cooldown = 0
    _queue_now = time.time()
    for _candidate in live_queue:
        if not isinstance(_candidate, dict):
            continue
        if str(_candidate.get("source") or "vuurland").strip() not in RADIO_SOURCE_ORDER:
            continue
        if _v41_cooldown_until(_candidate) > _queue_now:
            key = (f"{normalize_match(_candidate.get('artist', ''))}|||"
                   f"{normalize_match(_candidate.get('title', ''))}")
            if cache.get(f"__not_found_v{MATCHING_RULES_VERSION}__" + key) is not None:
                _radio_not_found_cooldown += 1
            else:
                _radio_short_cooldown += 1
        else:
            _radio_ready += 1
    print(f"📻 Radio-wachtrij: {_radio_ready} zoekklaar, "
          f"{_radio_short_cooldown} wacht op andere zoekstrategie, "
          f"{_radio_not_found_cooldown} in 24-uurs cooldown.")
    _source_counts = {source: 0 for source in source_order}
    for _candidate in live_queue:
        if not isinstance(_candidate, dict):
            continue
        _source = str(_candidate.get("source") or "vuurland").strip()
        if _source in _source_counts and _v41_cooldown_until(_candidate) <= _queue_now:
            _source_counts[_source] += 1
    print("📊 v120 wachtrij per bron: "
          + ", ".join(f"{name}={_source_counts[name]} zoekklaar" for name in source_order)
          + "; gezamenlijke FIFO zonder bronvoorrang.")

    # v120: oudste beschikbare nummer, ongeacht radiobron.

    for _queue_slot in range(max_queue_items_per_round):
        if not live_queue or additions_this_round >= max_additions_per_round:
            break

        selected_index = None
        selected_source = None
        waiting_for_retry = False
        now = time.time()

        # v120: sorteer ALLE twaalf bronnen op hun onveranderlijke FIFO-nummer.
        # Tijdelijke cooldowns en reeds geprobeerde items worden overgeslagen,
        # maar blijven bewaard voor latere sync-rondes.
        candidates = sorted(
            ((index, candidate) for index, candidate in enumerate(live_queue)
             if isinstance(candidate, dict)
             and str(candidate.get("source") or "vuurland").strip() in source_order),
            key=lambda pair: (pair[1].get("_v116_fifo_seq", 10**30), pair[0]),
        )
        for index, candidate in candidates:
            if id(candidate) in processed_item_ids:
                continue
            if now < _v41_cooldown_until(candidate):
                waiting_for_retry = True
                continue
            candidate_key = (f"{normalize_match(candidate.get('artist', ''))}|||"
                             f"{normalize_match(candidate.get('title', ''))}")
            if searches_used >= MAX_SEARCHES_PER_RUN:
                known_in_playlist = candidate_key in playlist_keys
                known_match = (f"__match_v{MATCHING_RULES_VERSION}__" + candidate_key) in cache
                if not (known_in_playlist or known_match or candidate_key in seen):
                    continue
            selected_index = index
            selected_source = str(candidate.get("source") or "vuurland").strip()
            break

        if selected_index is None:
            if waiting_for_retry:
                print("⏳ Alternatieve Spotify-zoekpogingen wachten; "
                      "geen ander nummer klaar voor verwerking.")
            break

        # De bestaande verwerking verwacht zijn gekozen item op positie nul.
        if selected_index != 0:
            selected_item = live_queue.pop(selected_index)
            live_queue.insert(0, selected_item)

        print(f"🔢 v120 gezamenlijke FIFO: volgnummer "
              f"{live_queue[0].get('_v116_fifo_seq')} geselecteerd "
              f"(bron: {selected_source}).")
        processed_item_ids.add(id(live_queue[0]))

        # Nooit ISRC-metadata van het vorige queue-item hergebruiken.
        LAST_SPOTIFY_MATCH_ISRC = None

        item = live_queue[0]

        # v34: herstartbestendige wachttijd tussen zoekstrategieën.
        # De queue blijft persistent in vuurland_live_queue.json.
        retry_at = int(item.get("_v34_retry_at", 0) or 0)
        if (retry_at and time.time() < retry_at
                and not (item.get('source') == 'duyster' and
                         f"{normalize_match(item.get('artist', ''))}|||{normalize_match(item.get('title', ''))}"
                         in duyster_confirmed_links)):
            live_queue.append(live_queue.pop(0))
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            print("⏳ Alternatieve Spotify-zoekpoging wacht tot later.")
            continue

        artist = v110_correct_radio_artist(item["artist"], item.get("source", ""))
        if artist != item["artist"]:
            print(f"🛠️ RadioBox-artiest gecorrigeerd: {item['artist']} → {artist}")
            item["artist"] = artist
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
        title = item["title"]

        # v131: extra veiligheidscontrole vóór iedere Spotify-zoekactie/toevoeging.
        if v131_block_nonlatin_east_asian(artist, title):
            print(f"⏭️ v131: Japanse/Chinese/Koreaanse tekens overgeslagen: {artist} — {title}")
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            continue


        # v119: titelcheck vóór elke Spotify Search, onafhankelijk van artiestenland.
        if v119_is_german_title(title):
            print(f"⛔ v119 Duitse titel geblokkeerd: {artist} — {title}")
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            continue

        language_decision = v106_language_decision(artist, title)
        if language_decision == "review":
            # v107: onbekende taal registreren, maar sync niet stilleggen.
            # Alleen expliciet bevestigde Duitse zang wordt geblokkeerd.
            print(f"📝 Taal nog niet beoordeeld (sync gaat door): {artist} — {title}")
        if language_decision == "block":
            print(f"⏭️ Duitstalige zang geblokkeerd: {artist} — {title}")
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            continue

        # v119: artiestenland speelt GEEN rol meer. Geen MusicBrainz-calls,
        # geen land-cooldown en geen Duitse-artiestenblokkering.
        # Bevestigde Duitse zang blijft wel geblokkeerd.

        if is_confirmed_german_vocal(artist, title):
            print(f"⏭️ Bevestigde Duitse zang overgeslagen: {artist} — {title}")
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            continue

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

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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
            (
                "golden smog",
                "love & mercy live on vin scelsa's idiot's delight 4/14/96",
            ),
            # Door gebruiker als niet beschikbaar op Spotify bevestigd.
            ("michael penn", "no myth (acoustic)"),
            ("ray lamontagne", "achin all the time"),
            ("jerry douglas", "the hymn of ordinary motion"),
            ("suzanne vega", "cassidy"),
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

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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
            v83_clear_resolved_failures(cache, artist, title)

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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

        linked_duyster_match = (
            duyster_confirmed_links.get(cache_key)
            if item.get('source') == 'duyster' else None
        )
        not_found_time = cache.get(
            not_found_key
        )

        if (
            linked_duyster_match is None
            and not_found_time is not None
            and time.time() - not_found_time
            < NOT_FOUND_COOLDOWN_SECONDS
        ):

            # Het nummer blijft behouden, maar gaat achteraan
            # de queue zodat andere nummers eerst verwerkt worden.
            failed_item = live_queue.pop(0)
            live_queue.append(failed_item)

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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

        # Radiomissers na vijf echte, mislukte zoekacties niet meer zoeken.
        # Geen blokkering van bestaande positieve Spotify-matches.
        radio_source = item.get('source', 'duyster')
        if (radio_source in ('vuurland', 'mellow_mix', 'big_sonic_heaven')
                and match_cache_key not in cache
                and v51_radio_failed_count(cache, artist, title) >= RADIO_FAILED_SEARCH_LIMIT):
            v51_radio_park(cache, artist, title, radio_source,
                           v51_radio_failed_count(cache, artist, title))
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
            print(f'🗃️ Radio: na vijf mislukte Spotify-zoekacties geparkeerd: {artist} - {title}')
            continue

        # v101: harde uitsluiting vóór cache, archiefkoppeling en Spotify Search.
        # Ook oudere positieve cachevermeldingen mogen dit niet omzeilen.
        if v101_radio_key(artist, title) in V101_EXCLUDED_RADIO_TRACKS:
            print(f"⏭️ v101: expliciet uitgesloten: {artist} - {title}")
            live_queue.pop(0)
            seen.add(cache_key)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_seen(seen)
            save_cache(cache)
            continue

        # ---------------------------------
        # CACHE SEARCH RESULT
        # ---------------------------------

        if linked_duyster_match:
            uri, known_isrc = linked_duyster_match
            # Local metadata is never a previous Search result.
            spotify_uri_isrc[uri] = known_isrc
            print(f'🔗 Duyster-archiefkoppeling (geen Search): {artist} - {title}')

        elif match_cache_key in cache:

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

                atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

                save_cache(cache)
                continue

            print(
                f"🔎 Spotify zoeken: "
                f"{artist} - {title}"
            )

            try:

                uri = find_spotify_track(
                    artist,
                    title,
                    search_variant=int(item.get("_v34_search_variant", 0) or 0),
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
                if LAST_SPOTIFY_MATCH_METADATA:
                    v80_record_confirmed(cache, artist, title,
                                         LAST_SPOTIFY_MATCH_METADATA[0],
                                         LAST_SPOTIFY_MATCH_METADATA[1], uri)
                    v82_remember_catalog(cache, artist, title, uri, LAST_SPOTIFY_MATCH_METADATA)
                v83_clear_resolved_failures(cache, artist, title)
                cache.get('__v51_radio_failed_cycles', {}).pop(_v47_key(artist,title),None)
                cache.get('__v51_radio_unmatched', {}).pop(_v47_key(artist,title),None)
                cache.get('__v51_radio_failed_searches', {}).pop(_v47_key(artist,title),None)

                # Een eerdere mislukte zoekpoging is niet meer relevant.
                cache.pop(not_found_key, None)

                save_cache(cache)

        # ---------------------------------
        # NIET GEVONDEN
        # ---------------------------------

        if uri is None:

            failed_source = item.get('source', 'duyster')
            if failed_source in ('vuurland', 'mellow_mix', 'big_sonic_heaven'):
                key = v51_radio_failure_key(artist, title)
                counts = cache.setdefault('__v51_radio_failed_searches', {})
                count = int(counts.get(key, 0) or 0) + 1
                counts[key] = count
                if count >= RADIO_FAILED_SEARCH_LIMIT:
                    v51_radio_park(cache, artist, title, failed_source, count)
                    live_queue.pop(0)
                    atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
                    save_cache(cache)
                    print(f'🗃️ Radio: {artist} - {title} na {count} mislukte zoekacties geparkeerd.')
                    print(f'🔎 Spotify Search gebruikt: {searches_used}/{MAX_SEARCHES_PER_RUN}')
                    continue

            print(
                f"⚠️ Geen betrouwbare Spotify-match gevonden: "
                f"{artist} - {title}"
            )

            print(
                "ℹ️ Dit betekent niet dat het nummer niet op Spotify "
                "bestaat; alleen dat de huidige zoekactie geen "
                "veilige match opleverde."
            )

            # v34: na een mislukte zoekopdracht twee andere strategieën
            # proberen op afzonderlijke sync-rondes, nooit in dezelfde ronde.
            attempt = int(item.get("_v34_search_variant", 0) or 0)
            if attempt < 2:
                item["_v34_search_variant"] = attempt + 1
                item["_v34_retry_at"] = int(time.time()) + 600
                live_queue.append(live_queue.pop(0))
                atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
                save_cache(cache)
                print(f"🔁 Geen match; zoekstrategie {attempt + 1}/2 "
                      "wordt in een latere ronde geprobeerd.")
                print(f"🔎 Spotify Search gebruikt: "
                      f"{searches_used}/{MAX_SEARCHES_PER_RUN}")
                continue

            # Pas na alle veilige zoekstrategieën: 24-uurs cooldown.
            cache[not_found_key] = int(time.time())
            failed_source = item.get("source", "duyster")
            v47_remember_failed(cache, artist, title, failed_source)
            if failed_source == "duyster":
                print("🗃️ Duyster: na 3 zoekstrategieën niet gevonden; uit de "
                      "automatische shuffle verwijderd (registratie bewaard).")
            else:
                if _v47_key(artist,title) in cache.get('__v51_radio_unmatched', {}):
                    print('🗃️ Radio: twee volledige zoekreeksen zonder match; '
                          'geparkeerd tot de volgende matcherverbetering.')
                else:
                    print('🗂️ Radio: na 24 uur één laatste volledige zoekreeks.')

            # Uit de huidige queue-positie verwijderen.
            #
            # Het nummer wordt NIET vergeten: de __not_found__
            # cooldown-cache zorgt ervoor dat het later opnieuw
            # geprobeerd kan worden.
            live_queue.pop(0)

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

            save_cache(cache)

            print(
                f"📋 {len(live_queue)} nummers "
                "blijven in live queue."
            )

            if _v47_key(artist,title) in cache.get('__v51_radio_unmatched', {}) or failed_source == 'duyster':
                print('🕒 Geparkeerd: niet opnieuw zoeken zonder matcherupdate.')
            else:
                print('🕒 Pas na 24 uur opnieuw zoeken.')

            print(
                f"🔎 Spotify Search gebruikt: "
                f"{searches_used}/{MAX_SEARCHES_PER_RUN}"
            )

            continue

        # v102: voorkom toevoegen via Spotify-cache of een cataloguslocator.
        if is_blocked_german_spotify_uri(uri):
            print(f"⏭️ v102: Duitstalige Spotify-opname geblokkeerd: {artist} — {title}")
            live_queue.pop(0)
            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)
            save_cache(cache)
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
            v83_clear_resolved_failures(cache, artist, title)

            save_seen(seen)
            save_cache(cache)

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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
            v83_clear_resolved_failures(cache, artist, title)

            save_seen(seen)
            save_cache(cache)

            atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

            continue

        # ---------------------------------
        # TOEVOEGEN AAN SPOTIFY
        # ---------------------------------

        # Alleen in de laatste 10 plaatsen doen we een exacte Spotify-count.
        # Daardoor zijn er maximaal 10 extra GET-calls per volledig volume.
        if active_playlist_count >= VOLUME_LIMIT - VOLUME_EXACT_COUNT_GUARD:
            active_playlist_count = _get_playlist_total(playlist_id)
            cache["__vuurland_active_playlist_count"] = active_playlist_count
            save_cache(cache)

            if active_playlist_count >= VOLUME_LIMIT:
                (
                    playlist_id,
                    active_volume_number,
                    active_playlist_count,
                ) = get_active_volume_playlist(cache)

        add_tracks(
            playlist_id,
            [uri]
        )

        active_playlist_count += 1
        cache["__vuurland_active_volume"] = active_volume_number
        cache["__vuurland_active_playlist_id"] = playlist_id
        cache["__vuurland_active_playlist_count"] = active_playlist_count
        save_cache(cache)

        # Vanaf Vol. 1 wordt elke nieuwe toevoeging ook geliket.
        # Hiervoor wordt dezelfde URI gebruikt: GEEN extra Spotify Search.
        if active_volume_number >= 1:
            _attempt_library_like(cache, uri)

        # Meteen lokaal als bestaande Spotify-URI markeren.
        # Zo kan dezelfde URI later in deze run niet opnieuw
        # worden toegevoegd.
        playlist_uris.add(uri)

        if candidate_isrc:
            playlist_isrcs.add(candidate_isrc)
            spotify_uri_isrc[uri] = candidate_isrc

        additions_this_round += 1
        if item.get('source') == 'duyster':
            duyster_additions_this_round += 1
        print(
            f"✅ Toegevoegd: "
            f"{artist} - {title}"
        )

        # Meteen lokaal als bestaand markeren.
        playlist_keys.add(cache_key)
        # Bewaar ook een versie-onafhankelijke sleutel meteen na toevoegen.
        radio_core = v71_core_song_title(title)
        if radio_core:
            for radio_artist in normalize_radio_artists(artist):
                playlist_keys.add(f"{radio_artist}|||{radio_core}")

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
        v83_clear_resolved_failures(cache, artist, title)
        save_seen(seen)

        atomic_save_json(live_queue_file, live_queue, indent=2, ensure_ascii=False)

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
        # Alleen expliciete Spotify-429/cooldown als herstelbare code 75.
        # Andere fouten blijven echte fouten, zodat de runner niet blind doorgaat.
        if isinstance(error, RuntimeError) and (
            "Spotify 429:" in str(error)
            or "Spotify rate-limit is nog actief" in str(error)
            or "Spotify Search HTTP 500: tijdelijke serverfout" in str(error)
            or "Spotify Search HTTP 502: tijdelijke serverfout" in str(error)
            or "Spotify Search HTTP 503: tijdelijke serverfout" in str(error)
            or "Spotify Search HTTP 504: tijdelijke serverfout" in str(error)
            or "Spotify HTTP 403:" in str(error)
            or "Spotify tijdelijke serverpauze is nog actief" in str(error)
        ):
            stored = load_cache()
            until = max(float(stored.get("__spotify_api_blocked_until", 0) or 0),
                        float(stored.get("__spotify_server_error_until", 0) or 0))
            if until > time.time():
                print("⏸️ v70: volgende 2-minutenronde wordt RADIO-ONLY.")
                raise SystemExit(75)
        raise
