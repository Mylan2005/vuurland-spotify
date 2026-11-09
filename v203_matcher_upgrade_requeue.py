"""v203: automatically reconsider known failures AFFECTED by tested matcher changes.

A release is a FIFO retry, NOT an approved Spotify match. Each new matcher
rule must be added explicitly to this registry together with regression tests.
No network calls, no cache-wide resets, no fabricated source or song.
"""
import time

from duyster_archive_fifo import DUYSTER_MAX_PENDING, DUYSTER_MAX_TOTAL_QUEUE

from v194_matcher_metadata import canonical_artist, canonical_title
from v200_verified_catalog_titles import verified_catalog_title
from v208_explicit_artist_feature import verified_report_album_hint
from v211_report_search_rescue import (
    album_hint as v211_album_hint,
    confirmed_guest_credit as v211_confirmed_guest,
    mint_julep_catalog_search_title as v211_mint_title,
    unconfirmed_song_search as v211_unconfirmed_query,
)
from v209_verified_source_title import verified_emily_live_source_title
from v207_verified_matcher_metadata import (
    verified_artist_search_name,
    verified_balthazar_castle_version,
)

# Update this registry *in the same tested PR* as any future matcher fix.
# No general "retry everything whenever code changed" behavior.
MATCHER_RETRY_RULES = (
    "v199_exact_trailing_artist",
    "v200_tired_pony_verified_catalog_title",
    "v194_reversed_the_artist_credit",
    "v207_fink_uk_exact_title",
    "v207_giraffe_chinese_full_artist",
    "v207_balthazar_castle_named_version",
    "v208_parenthesized_feature",
    "v208_plusminus_exact_album_artist",
    "v208_verified_album_query",
    "v209_emily_live_exact_source_spelling",
    "v211_verified_original_album_search",
    "v211_verified_lucy_ryan_artist",
    "v211_verified_mint_julep_single",
    "v211_unconfirmed_catalog_safe_search",
)
_RULE_HISTORY = "__v203_matcher_upgrade_retried_rules"
_LAST_RELEASE = "__v203_matcher_upgrade_last_release"
_MIN_GAP = 6 * 3600  # At most one matcher-upgrade recovery every six hours.
# Reuse the archive FIFO backpressure limits: never revive the obsolete 100/3600 caps.


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
    # De nieuwe regels gelden ALLEEN voor aantoonbaar dezelfde bronmetadata.
    # Requeue betekent opnieuw laten VALIDEREN, niet automatisch accepteren.
    if (artist.strip().casefold() == "fink (uk)"
            and title.strip().casefold() == "looking too closely"
            and verified_artist_search_name(artist, title) == "Fink"):
        hits.append("v207_fink_uk_exact_title")
    if (artist.strip().casefold() == "the giraffe told me in my dream"
            and title.strip().casefold() == "before"
            and verified_artist_search_name(artist, title) == "我夢見長頸鹿對我說"):
        hits.append("v207_giraffe_chinese_full_artist")
    if verified_balthazar_castle_version(
            artist, title, "Balthazar", "On A Roll - Sand Castle Tapes"):
        hits.append("v207_balthazar_castle_named_version")
    # Bron en Spotify bevestigen UNKLE + Ian Brown voor Be There.
    # Alleen deze bewezen eerdere misser krijgt een beheerste FIFO-herkansing.
    if (artist.strip().casefold() == "unkle (feat. ian brown)"
            and title.strip().casefold() == "be there"):
        hits.append("v208_parenthesized_feature")
    # Eén gecontroleerde retry voor exact bevestigde song/album-metadata.
    # Spotify moet nog steeds de VOLLEDIGE track veilig valideren.
    if (artist.strip().casefold() == "plusminus"
            and title.strip().casefold() in {"rewrite the story", "jumping the tracks"}):
        hits.append("v208_plusminus_exact_album_artist")
    if verified_report_album_hint(artist, title) and artist.strip().casefold() != "plusminus":
        hits.append("v208_verified_album_query")
    if verified_emily_live_source_title(artist, title) != title.strip():
        hits.append("v209_emily_live_exact_source_spelling")
    # v211: alleen de 20 oorspronkelijke, echte missers uit rapporten 45/46.
    # De bronidentiteit komt verplicht uit bewaarde mislukte zoekresultaten.
    # De herprobeerde song blijft aan de originele FIFO + matcher gebonden.
    if v211_album_hint(artist, title):
        hits.append("v211_verified_original_album_search")
    if v211_confirmed_guest(artist, title) != artist.strip():
        hits.append("v211_verified_lucy_ryan_artist")
    if v211_mint_title(artist, title):
        hits.append("v211_verified_mint_julep_single")
    if v211_unconfirmed_query(artist, title):
        hits.append("v211_unconfirmed_catalog_safe_search")
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

        if len(live_queue) >= DUYSTER_MAX_TOTAL_QUEUE:
            break
        if source == "duyster" and sum(
            1 for item in live_queue if isinstance(item, dict)
            and item.get("source") == "duyster"
        ) >= DUYSTER_MAX_PENDING:
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
