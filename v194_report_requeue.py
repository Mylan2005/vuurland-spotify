"""v194: éenmalige, gerichte herkansing na rapporten 32–43.

Niet de 146 rapportregels blind hervullen! Alleen gecontroleerde structurele
false negatives. Originele bron uitsluitend uit bestaande radio-/Duyster-state,
geen fictieve uitzendingen. Geen Spotify-call of scanner. FIFO nooit herschikken.
"""

# Alleen gevallen met een concreet, door de nieuwe *generieke* regels
# verklaard artiest-/titelprobleem én een gelijknamige Spotify-kandidaat.
REVIEWED = (
    ("Birkii", "Holy War - Birkii"),
    ("Nada Surf", "Where Is My Mind? - Nada Surf"),
    ("The 6ths With Lloyd Cole", "Human (featuring Lloyd Cole) - The 6ths With Lloyd Cole"),
    ("Eva & Manu", "Empty"),
    ("Santogold", "The Riot's Gone"),
    ("Decemberists, The", "The Engine Driver"),
    ("Dog Is Dead", "Talent Show"),
    ("EoB", "Brasil"),
    ("Roberta Flack", "The First Time Ever I Saw Your"),
    ("Urlaub In Polen", "The Velvet Blues (Ext. Version)"),
)
_DONE = "__v194_reviewed_reports_32_43_retried"


def release_report_retries(cache, live_queue, seen, *, active_sources,
                           make_key, in_playlist, eligible):
    """Retry only previously observed, still missing, eligible report entries.

    Returns (new_items, existing_queue_items_released, unresolved_source).
    """
    done = set(cache.get(_DONE, []) or [])
    indexed = {make_key(x.get("artist", ""), x.get("title", "")): x
               for x in live_queue if isinstance(x, dict)}
    playlist_keys = set(cache.get("__playlist_keys", []) or [])
    discovered = cache.get("__v47_radio_discovered", {}) or {}
    failed = cache.get("__v47_failed_tracks", {}) or {}
    parked = cache.get("__v51_radio_unmatched", {}) or {}
    duyster_miss = cache.get("__v50_duyster_unmatched", {}) or {}
    released, refreshed, no_source = 0, 0, 0

    def clean_one(key):
        # Alleen het exacte, gecontroleerde nummer. Geen globale cache-reset.
        for store in ("__v47_failed_tracks", "__v51_radio_unmatched",
                      "__v51_radio_failed_searches", "__v51_radio_failed_cycles"):
            mapping = cache.get(store)
            if isinstance(mapping, dict):
                mapping.pop(key, None)
        for version in (34, 35):
            cache.pop(f"__not_found_v{version}__" + key, None)

    for artist, title in REVIEWED:
        key = make_key(artist, title)
        if key in done:
            continue
        if not eligible(artist, title):
            # Blokkades van de gebruiker hebben altijd voorrang.
            continue
        if key in seen or key in playlist_keys or in_playlist(artist, title, playlist_keys):
            done.add(key)
            continue
        if key in indexed:
            item = indexed[key]
            if item.get("source") not in (*active_sources, "duyster"):
                continue
            # Zelfde object/plek/volgnummer: alleen een bestaande mislukte
            # poging opnieuw vrijgeven, geen duplicaat achteraan plaatsen.
            item.pop("_v34_retry_at", None)
            item["_v34_search_variant"] = 0
            clean_one(key)
            done.add(key)
            refreshed += 1
            continue

        # Neem eerst de ECHTE oorspronkelijke bron uit een retryregistratie.
        entry = parked.get(key) or failed.get(key)
        src = entry.get("source") if isinstance(entry, dict) else None
        if src not in active_sources:
            src = next((source for source in active_sources
                        if key in set(discovered.get(source, []) or [])), None)
        if src is None and key in duyster_miss:
            src = "duyster"  # alleen als Duyster deze identiteit echt archiveerde
        if src not in (*active_sources, "duyster"):
            no_source += 1
            continue

        live_queue.append({"artist": artist, "title": title, "source": src,
                           "_v34_search_variant": 0})
        indexed[key] = live_queue[-1]
        if src == "duyster" and isinstance(duyster_miss, dict):
            duyster_miss.pop(key, None)
        clean_one(key)
        done.add(key)
        released += 1
        print(f"♻️ v194 veilige matcherherkansing achteraan FIFO: "
              f"[{src}] {artist} — {title}")

    cache[_DONE] = sorted(done)
    if released or refreshed or no_source:
        print(f"🔎 v194: {released} eerder gemiste nummers opnieuw in FIFO, "
              f"{refreshed} bestaande wachters ontgrendeld; "
              f"{no_source} zonder bewezen oorspronkelijke bron overgeslagen.")
    return released, refreshed, no_source
