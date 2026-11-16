"""v249: POST 5xx never imposes global pause; other tracks continue."""
from pathlib import Path
from v248_spotify_post_guard import post_5xx_cooldown_seconds

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
start = src.index("def spotify_request(")
end = src.index("\ndef get_playlist(", start)
api = src[start:end]
assert "post_5xx_cooldown_seconds(" not in api
assert 'cache["__v247_uncertain_playlist_appends"]' in api
assert 'cache["__v242_uncertain_playlist_append"]' in api
assert '"tijdelijke serverfout; status van toevoeging onzeker."' in api
assert "tijdelijke serverfout na tokenvernieuwing; status van toevoeging onzeker." in api
sync = src[src.index("def sync("):]
assert 'except RuntimeError as error:' in sync
assert 'str(error).startswith("Spotify playlist POST HTTP ")' in sync
assert 'item["_v34_retry_at"] = int(time.time()) + 3600' in sync
assert 'live_queue.append(live_queue.pop(0))' in sync
assert "verify_uncertain_spotify_append" not in src
print("✅ v249: 502-POST zonder globale pauze, FIFO veilig bewaard.")
