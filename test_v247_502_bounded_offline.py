"""v247: never scan entire playlist or blindly re-post an uncertain URI."""
from pathlib import Path
src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
start = src.index("def add_tracks(")
end = src.index("\ndef get_track_isrc_from_uri", start)
body = src[start:end]
assert "verify_uncertain_spotify_append" not in src
assert 'params={"limit": 100, "offset": max(0, total - 100)}' in body
assert "return None" in body and "return False" in body
assert body.index("return None") < body.index('spotify_request(\n            "POST"')
assert "__v247_uncertain_playlist_appends" in body
assert 'if was_added is None:' in src
assert 'live_queue.append(live_queue.pop(0))' in src[src.index('if was_added is None:'):]
assert '"__v247_uncertain_playlist_appends"' in src
print("✅ v247: maximaal 100 recente items, onzekere POST nooit blind opnieuw, FIFO blijft doorlopen.")
