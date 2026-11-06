"""v203: automatically reconsider known failures AFFECTED by tested matcher changes.

A release is a FIFO retry, NOT an approved Spotify match. Each new matcher
rule must be added explicitly to this registry together with regression tests.
No network calls, no cache-wide resets, no fabricated source or song.
"""
import time

from v194_matcher_metadata import canonical_artist, canonical_title
from v200_verified_catalog_titles import verified_catalog_title

# Update this registry *in the same tested PR* as any future matcher fix.
# No general "retry everything whenever code changed" behavior.
MATCHER_RETRY_RULES = (
    "v199_exact_trailing_artist",
    "v200_tired_pony_verified_catalog_title",
    "v194_reversed_the_artist_credit",
)
_RULE_HISTORY = "__v203_matcher_upgrade_retried_rules"
_LAST_RELEASE = "__v203_matcher_upgrade_last_release"
_MIN_GAP = 6 * 3600  # At most one matcher-upgrade recovery every six hours.
_QUEUE_MAX = 3600
_DUYSTER_MAX = 100


def applicable_rules(artist, title):
    """Which explicit, tested matcher improvements address this metadata?"""
    if not isinstance(artist, str) or not isinstance(title, str):
        return ()
    if not artist.strip() or not title.strip():
        return ()
    hits = []
    # Canonicalization may delete a trailing credit only if it repeats the
    # COMPLETE source artist; ordinary song/version suffixes remain intact.
    if canonical_title(artist, title) != title.strip():
        hits.append("v199_exact_trailing_artist")
    # The official catalog title is explicitly confirmed; no fuzzy guessing.
    if verified_catalog_title(artist, title, "All Things All At Once"):
        hits.append("v200_tired_pony_verified_catalog_title")
    # Correct only "Lastname, The" -> "The Lastname"; Spotify still verifies.
    if canonical_artist(artist) != artist.strip():
        hits.append("v194_reversed_the_artist_credit")
    return tuple(rule for rule in MATCHER_RETRY_RULES if rule in hits)


def release_for_matcher_upgrades(
    cache, live_queue, seen, *, active_sources, make_key,
    in_playlist, eligible, now=None, max_per_round=1,
):
    """Release at most one proven relevant miss after matcher upgrades.

    Rules, identities and source evidence must all match; existing queue items
    are never reordered. All requeued tracks pass regular Spotify search and
    version, exclusion and ambiguity checks at their normal FIFO turn.
    Returns (appended, unlocked).
    """
    now = time.time() if now is None else float(now)
    if max_per_round < 1:
        return 0, 0
    try:
        last_global = float(cache.get(_LAST_RELEASE, 0) or 0)
    except (ValueError, TypeError, OverflowError):
        return 0, 0
    if last_global > now or (last_global > 0 and now - last_global < _MIN_GAP):
        return 0, 0

    retry_history = cache.get(_RULE_HISTORY, {})
    if not isinstance(retry_history, dict):
        return 0, 0
    parked = cache.get("__v51_radio_unmatched", {})
    failed = cache.get("__v47_failed_tracks", {})
    duyster = cache.get("__v50_duyster_unmatched", {})
    if not all(isinstance(mapping, dict) for mapping in (parked, failed, duyster)):
        return 0, 0

    queue_index = {
        make_key(item.get("artist", ""), item.get("title", "")): item
        for item in live_queue if isinstance(item, dict)
    }
    known_playlist = set(cache.get("__playlist_keys", []) or [])
    active = set(active_sources)
    allowed_sources = active | {"duyster"}
    appended = unlocked = 0

    # Preserve the cache's own insertion order, not popularity or searches:
    # one release per round, appended at the END of the normal FIFO.
    for key in dict.fromkeys((*parked, *failed, *duyster)):
        entry = parked.get(key) or failed.get(key) or duyster.get(key)
        if not isinstance(entry, dict):
            continue
        artist, title = entry.get("artist"), entry.get("title")
        if not isinstance(artist, str) or not isinstance(title, str):
            continue
        if make_key(artist, title) != key:
            continue  # never use corrupt/historical mismatched identities
        rules = applicable_rules(artist, title)
        previously = retry_history.get(key, [])
        if not isinstance(previously, list):
            continue
        new_rules = [rule for rule in rules if rule not in previously]
        if not new_rules:
            continue
        source = entry.get("source")
        # For Duyster we ONLY trust its explicit archive miss register.
        if source == "duyster":
            if key not in duyster:
                continue
        elif source not in active:
            continue
        if source not in allowed_sources:
            continue
        if not eligible(artist, title):
            continue
        if key in seen or key in known_playlist or in_playlist(artist, title, known_playlist):
            continue

        existing = queue_index.get(key)
        if existing is not None:
            # Already waiting: don't skip its FIFO position or unlock a
            # different artist/source. It will naturally be matched again.
            if existing.get("source") != source:
                continue
            # Make no mutation to its sequence, retry or cooldown metadata.
            retry_history[key] = sorted(set(previously) | set(new_rules))
            cache[_RULE_HISTORY] = retry_history
            continue

        if len(live_queue) >= _QUEUE_MAX:
            break
        if source == "duyster" and sum(
            1 for item in live_queue if isinstance(item, dict)
            and item.get("source") == "duyster"
        ) >= _DUYSTER_MAX:
            continue
        if appended >= max_per_round:
            break

        # Recover only this original observed item. Avoid global cache reset.
        live_queue.append({
            "artist": artist, "title": title, "source": source,
            "_v34_search_variant": 0,
        })
        queue_index[key] = live_queue[-1]
        for name in (
            "__v51_radio_unmatched", "__v47_failed_tracks",
            "__v50_duyster_unmatched", "__v51_radio_failed_searches",
            "__v51_radio_failed_cycles",
        ):
            mapping = cache.get(name)
            if isinstance(mapping, dict):
                mapping.pop(key, None)
        for version in (34, 35):
            cache.pop(f"__not_found_v{version}__" + key, None)

        retry_history[key] = sorted(set(previously) | set(new_rules))
        cache[_RULE_HISTORY] = retry_history
        cache[_LAST_RELEASE] = now
        appended += 1
        print(f"♻️ v203: matcherverbetering ({', '.join(new_rules)}) "
              f"herprobeert achteraan FIFO [{source}]: {artist} — {title}")
    return appended, unlocked
