"""v214: behoud eerder verwerkte Spotify-nummers na handmatige verwijdering.

De Spotify-playlist bepaalt welke items NU aanwezig zijn; de historische
dedupe-cache registreert welke opnames Vuurland OOIT heeft gezien. Een
bewuste verwijdering uit de playlist wordt daarmee automatisch gerespecteerd:
zonder extra API-verzoeken, afwijsformulier of handmatige GitHub-invoer.

Nooit een onvolledige scan publiceren. Alleen na succesvolle complete
paginering aanroepen; geen enkele Spotify-write.
"""


def preserve_processed_playlist_history(cache, scanned_keys, scanned_uris,
                                        scanned_isrcs, scanned_uri_isrc):
    """Merge complete Spotify scan with persisted history, without mutation.

    Historical entries are *not* proof that an item remains in the playlist;
    they are only a permanent no-readd record. This also preserves all old
    volumes and recently added tracks while a multi-round scan completes.
    """
    if not isinstance(cache, dict):
        raise ValueError("v214: ongeldige Spotify-cache")
    fields = ("__playlist_keys", "__playlist_uris", "__playlist_isrcs")
    for field in fields:
        if field in cache and not isinstance(cache[field], list):
            raise ValueError(f"v214: ongeldige historische cache: {field}")
    previous_uri_isrc = cache.get("__spotify_uri_isrc", {})
    if not isinstance(previous_uri_isrc, dict):
        raise ValueError("v214: ongeldige Spotify ISRC-mapping")
    keys = set(scanned_keys) | set(cache.get("__playlist_keys", []))
    uris = set(scanned_uris) | set(cache.get("__playlist_uris", []))
    isrcs = set(scanned_isrcs) | set(cache.get("__playlist_isrcs", []))
    uri_isrc = dict(previous_uri_isrc)
    uri_isrc.update(scanned_uri_isrc)
    return keys, uris, isrcs, uri_isrc
