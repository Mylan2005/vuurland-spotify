"""Adaptive pause after Spotify playlist POST 5xx; never retries a POST.

A 502 can be server-side and is impossible to eliminate at the client.
Keep the radio queue alive and reduce repeat failures without full scans.
"""


def post_5xx_cooldown_seconds(cache, now):
    """Backoff 3, 6, 12, 24, 30 minutes for repeated recent POST 5xx."""
    last = float(cache.get("__v248_last_playlist_post_5xx", 0) or 0)
    previous = int(cache.get("__v248_playlist_post_5xx_streak", 0) or 0)
    streak = min(5, previous + 1) if 0 <= now - last < 3600 else 1
    cache["__v248_last_playlist_post_5xx"] = now
    cache["__v248_playlist_post_5xx_streak"] = streak
    return min(180 * (2 ** (streak - 1)), 1800)


def after_successful_post(cache):
    """Clear streak only after a confirmed successful playlist POST."""
    had = "__v248_playlist_post_5xx_streak" in cache or "__v248_last_playlist_post_5xx" in cache
    cache.pop("__v248_playlist_post_5xx_streak", None)
    cache.pop("__v248_last_playlist_post_5xx", None)
    return had
