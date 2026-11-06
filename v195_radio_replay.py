"""v195: Let a genuinely new radio play retry a parked false negative safely.

No Spotify API calls here. Only a fresh replay observed by v96 may trigger
a retry. A failed search remains failed until the usual matcher proves a match.
"""
import time

REPLAY_INTERVAL_SECONDS = 30 * 24 * 3600
GLOBAL_INTERVAL_SECONDS = 24 * 3600
_LAST_GLOBAL = "__v195_radio_replay_last_release"
_LAST_BY_KEY = "__v195_radio_replay_last_by_key"


def release_parked_replay(cache, key, artist, title, source, *, now=None):
    """Release one proven parked radio miss, respecting persistent rate gates.

    Called only from the v96 new-arrival branch AFTER language, exclusion,
    seen, queue and playlist checks. The caller appends to FIFO after True.
    """
    now = time.time() if now is None else float(now)
    parked = cache.get("__v51_radio_unmatched", {})
    entry = parked.get(key) if isinstance(parked, dict) else None
    if not isinstance(entry, dict):
        return False
    if not artist or not title or not source:
        return False
    # Previous parking must identify the exact same track identity; never
    # infer a missing artist/title or invent a source from a report.
    if entry.get("artist") != artist or entry.get("title") != title:
        return False
    # Never replay an incomplete/invalid historical failure record as if it
    # had been parked decades ago. Be conservative on corrupt timestamps.
    def valid_timestamp(value):
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if 0 < value <= now else None

    failed_at = valid_timestamp(entry.get("failed_at"))
    if failed_at is None or now - failed_at < REPLAY_INTERVAL_SECONDS:
        return False
    last_by_key = cache.get(_LAST_BY_KEY, {})
    if not isinstance(last_by_key, dict):
        return False
    last = last_by_key.get(key)
    if last is not None:
        last = valid_timestamp(last)
        if last is None or now - last < REPLAY_INTERVAL_SECONDS:
            return False
    last_global = cache.get(_LAST_GLOBAL)
    if last_global is not None:
        last_global = valid_timestamp(last_global)
        if last_global is None or now - last_global < GLOBAL_INTERVAL_SECONDS:
            return False

    # Release ONLY this key. No broad reset and no changes to queue order.
    parked.pop(key, None)
    for name in ("__v47_failed_tracks", "__v51_radio_failed_searches",
                 "__v51_radio_failed_cycles"):
        mapping = cache.get(name)
        if isinstance(mapping, dict):
            mapping.pop(key, None)
    for version in (34, 35):
        cache.pop("__not_found_v%s__" % version + key, None)
    last_by_key[key] = now
    cache[_LAST_BY_KEY] = last_by_key
    cache[_LAST_GLOBAL] = now
    return True
