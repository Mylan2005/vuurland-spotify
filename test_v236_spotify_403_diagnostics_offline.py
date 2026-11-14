"""Offline safety: 403 endpoint/metadata privacy, cooldown, queue preservation."""
import ast
from pathlib import Path
from v236_spotify_403_diagnostics import safe_spotify_endpoint, safe_403_detail

assert safe_spotify_endpoint("/search?q=secret") == "/search"
assert safe_spotify_endpoint("/playlists/secret-playlist-id/items?x=1") == "/playlists/{id}/items"
assert safe_spotify_endpoint("/playlists/secret-playlist-id") == "/playlists/{id}"
assert safe_spotify_endpoint("/tracks/secret-track-id") == "/tracks/{id}"
assert safe_spotify_endpoint("/me/library?uris=secret") == "/me/library"
assert safe_spotify_endpoint("/users/secret-user-id/playlists") == "/overig"
assert safe_403_detail("POST", "/playlists/secret-id/items?uris=private", "Forbidden") == {
    "method": "POST", "endpoint": "/playlists/{id}/items", "reason": "forbidden"
}
assert safe_403_detail("PUT", "/me/library?uris=private", "Insufficient client scope")["reason"] == "insufficient client scope"
assert safe_403_detail("GET", "/search?q=private", "Account email somebody@example.com rejected")["reason"] == "geen veilige omschrijving"
assert "secret" not in str(safe_403_detail("GET", "/playlists/secret/items?track=secret", "secret"))

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
assert "cache[\"__v236_last_spotify_403\"]" in source
assert "time.time() + 3600" in source  # do not bypass Spotify denial
assert 'cache["__spotify_server_error_until"] = blocked_until' in source
assert '"recovered_at"' in source
assert "Spotify HTTP 403 bij {diagnosis['method']}" in source
assert "Spotify tijdelijke serverpauze is nog actief." in source
assert "raise SystemExit(75)" in source
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
print("✅ v236: foutendpoint geanonimiseerd + 60m cooldown + succesvolle hervatting bewaakt.")
