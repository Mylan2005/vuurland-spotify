"""Offline v248 adaptive 5xx cooldown and POST safety checks."""
from pathlib import Path
from v248_spotify_post_guard import post_5xx_cooldown_seconds, after_successful_post

cache = {}
assert [post_5xx_cooldown_seconds(cache, 1000 + i * 200) for i in range(5)] == [
    180, 360, 720, 1440, 1800
]
assert cache["__v248_playlist_post_5xx_streak"] == 5
assert post_5xx_cooldown_seconds(cache, 6000) == 180
assert after_successful_post(cache)
assert not after_successful_post(cache)
assert post_5xx_cooldown_seconds(cache, 6200) == 180

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert src.count("post_5xx_cooldown_seconds(cache, time.time())") == 2
assert 'and re.fullmatch(r"/playlists/[^/]+/items", _library_path)' in src
assert "verify_uncertain_spotify_append" not in src
assert 'params={"limit": 100, "offset": max(0, total - 100)}' in src
assert "raise RuntimeError(\n                    f\"Spotify playlist POST HTTP {response.status_code}:" in src
assert 'if was_added is None:' in src
print("✅ v248: herhaalde 5xx krijgen oplopende pauze; geen blinde POST-retry of volledige scan.")
