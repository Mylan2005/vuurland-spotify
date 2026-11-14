"""v236: veilige diagnose van Spotify 403 zonder tokens, IDs of querystrings.

Geen automatische tokenrevoke, geen vervroegde retries, geen Spotify-call.
De bestaande 60-minutenpauze, FIFO en alle autorisatiechecks blijven intact.
"""
import re


def safe_spotify_endpoint(endpoint):
    """Maak API-routes herkenbaar zonder privé-playlist-ID's of track-ID's."""
    path = str(endpoint or "").split("?", 1)[0].strip()
    path = re.sub(r"/playlists/[^/]+", "/playlists/{id}", path)
    path = re.sub(r"/tracks/[^/]+", "/tracks/{id}", path)
    path = re.sub(r"/artists/[^/]+", "/artists/{id}", path)
    path = re.sub(r"/albums/[^/]+", "/albums/{id}", path)
    if path not in {"/search", "/me", "/me/playlists", "/me/library"} and not (
        re.fullmatch(r"/playlists/\{id\}/(?:items|tracks)?", path)
        or re.fullmatch(r"/tracks/\{id\}", path)
        or re.fullmatch(r"/artists/\{id\}", path)
        or re.fullmatch(r"/albums/\{id\}", path)
    ):
        return "/overig"
    return path


def safe_403_detail(method, endpoint, message):
    """Log alleen foutstatus, methode en geredigeerd pad, nooit Spotify-secrets."""
    verb = str(method or "").upper()
    if verb not in {"GET", "POST", "PUT", "DELETE"}:
        verb = "OTHER"
    path = safe_spotify_endpoint(endpoint)
    # Spotify's error.message kan persoonsgegevens of IDs bevatten.
    # Alleen een klein stel officiële generieke redenen publiek loggen.
    detail = str(message or "").strip().casefold()
    if detail in {"forbidden", "insufficient client scope",
                  "insufficient scope", "user not registered in the developer dashboard"}:
        reason = detail
    else:
        reason = "geen veilige omschrijving"
    return {"method": verb, "endpoint": path, "reason": reason}
