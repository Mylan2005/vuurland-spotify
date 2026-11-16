"""Fail-closed reconciliation of one uncertain Spotify playlist append.

Only invoked after a previous playlist POST returned HTTP 5xx. A playlist
snapshot must remain unchanged throughout the entire scan; otherwise the
caller must pause rather than risk a duplicate.
"""


def verify_uncertain_spotify_append(request, playlist_id, uri):
    """Return True if URI already exists, False only after a stable full scan."""
    endpoint = f"/playlists/{playlist_id}"
    before = request("GET", endpoint, params={"fields": "snapshot_id"})
    snapshot = before.get("snapshot_id") if isinstance(before, dict) else None
    if not isinstance(snapshot, str) or not snapshot:
        raise RuntimeError("Spotify 502-herstel: playlist-snapshot ontbreekt.")

    total = None
    found = False
    offset = 0
    while True:
        page = request(
            "GET", f"/playlists/{playlist_id}/items",
            params={"limit": 100, "offset": offset},
        )
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise RuntimeError("Spotify 502-herstel: onvolledige playlist-pagina.")
        count = page.get("total")
        if type(count) is not int or count < 0 or count > 10000:
            raise RuntimeError("Spotify 502-herstel: ongeldig playlist-aantal.")
        if total is None:
            total = count
        elif count != total:
            raise RuntimeError("Spotify 502-herstel: playlist veranderd tijdens scan.")
        items = page["items"]
        expected = min(100, total - offset)
        if len(items) != expected:
            raise RuntimeError("Spotify 502-herstel: onvolledige playlist-scan.")
        for entry in items:
            if not isinstance(entry, dict):
                raise RuntimeError("Spotify 502-herstel: ongeldig playlist-item.")
            track = entry.get("item") or entry.get("track")
            if not isinstance(track, dict):
                raise RuntimeError("Spotify 502-herstel: trackgegevens ontbreken.")
            if track.get("uri") == uri:
                found = True
        offset += expected
        if offset >= total:
            break
        if expected == 0:
            raise RuntimeError("Spotify 502-herstel: scan maakt geen voortgang.")

    after = request("GET", endpoint, params={"fields": "snapshot_id"})
    if not isinstance(after, dict) or after.get("snapshot_id") != snapshot:
        raise RuntimeError("Spotify 502-herstel: playlist-snapshot gewijzigd.")
    return found
