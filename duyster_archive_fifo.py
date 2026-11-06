"""v192: Duyster-archief voorzichtig in de bestaande live-FIFO opnemen.

- Maximaal één archiefnummer per 120 seconden, ook na runnerherstarts.
- Geen Spotify-/netwerkvragen en geen automatische playlistinventaris.
- Willekeurige, reproduceerbare volgorde uit alle Duyster-afleveringen.
- Aflevering 833 staat in het archief maar krijgt geen oneerlijke voorrang.
- Hoogstens 100 wachtende Duyster-nummers en max. 3600 FIFO-items.
- Alle bestaande radio-items en hun volgorde blijven onaangeroerd.
"""
import csv
import hashlib
import os
import re
import random
import secrets
import time

DUYSTER_ENQUEUE_INTERVAL_SECONDS = 120
DUYSTER_MAX_PENDING = 100
DUYSTER_MAX_TOTAL_QUEUE = 3600
_CURSOR = "__v192_duyster_archive_cursor"
_NEXT = "__v192_duyster_next_enqueue_at"
_SHAPE = "__v192_duyster_archive_shape"
_SEED = "__v193_duyster_shuffle_seed"


def is_non_music_title(title):
    """Alleen zuivere rubriektitels zijn geen muziek, niet echte songnamen."""
    value = str(title or "").replace(chr(160), " ").strip()
    # De website zet soms een rubriek tussen haakjes.
    if len(value) > 2 and value[0] + value[-1] in ("()", "[]"):
        value = value[1:-1].strip()
    return bool(re.fullmatch(
        r"(?:interview|sessie|interview\s*[+&]\s*sessie|radio\s*1\s*sessie)",
        value, re.IGNORECASE,
    ))


def canonical_duyster_title(title):
    """Gebruik de gewone opnametitel als een Radio 1 Sessie-suffix staat vermeld.

    Alleen een expliciete afsluitende '(Radio 1 Sessie)' of '[Radio 1 Sessie]'
    verwijderen, niet 'Session' of 'Live' van andere artiesten/opnames.
    Geef None terug voor rubrieken zonder echt muzieknummer.
    """
    value = str(title or "").replace(chr(160), " ").strip()
    if not value or is_non_music_title(value):
        return None
    value = re.sub(
        r"\s*[\[(]\s*radio\s*1\s*sessie\s*[\])]\s*$",
        "", value, flags=re.IGNORECASE,
    ).strip()
    return value if value and not is_non_music_title(value) else None


def _load_candidates(data_dir, key_func):
    """Heel het archief inclusief aflevering 833, zonder dubbels."""
    paths = (
        (os.path.join(data_dir, "duyster_aflevering_833.csv"), ("artist", "title")),
        (os.path.join(data_dir, "duyster_archief_uniek.csv"), ("artist", "title")),
    )
    entries, used = [], set()
    for path, required in paths:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(required).issubset(reader.fieldnames or []):
                raise ValueError(f"Duyster-archief heeft geen artist/title-kolommen: {path}")
            for row in reader:
                artist = str(row.get("artist") or "").strip()
                title = canonical_duyster_title(row.get("title"))
                if not artist or not title:
                    continue
                key = key_func(artist, title)
                if key not in used:
                    used.add(key)
                    entries.append((artist, title, key))
    return entries


def enqueue_one(cache, live_queue, seen, *, data_dir, key_func,
                allowed, in_playlist, now=None):
    """Voeg hoogstens één gecheckt nummer ACHTERAAN toe; retourneer het item.

    De aanroeper bewaart bestaande FIFO en cache direct, atomisch en op dezelfde
    wijze als de acht radiozenders. Bij mislukte schijflezing: laat alles intact.
    """
    now = time.time() if now is None else float(now)
    if now < float(cache.get(_NEXT, 0) or 0):
        return None
    if len(live_queue) >= DUYSTER_MAX_TOTAL_QUEUE:
        print("⏸️ Duyster: totale FIFO-limiet; geen nieuwe archiefitems.")
        return None
    pending = sum(1 for x in live_queue if isinstance(x, dict)
                  and x.get("source") == "duyster")
    if pending >= DUYSTER_MAX_PENDING:
        print(f"⏸️ Duyster: {pending} wachtende archiefitems; rustig pauzeren.")
        return None

    try:
        candidates = _load_candidates(data_dir, key_func)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        print(f"⏭️ Duyster: archief niet betrouwbaar leesbaar ({error}); FIFO intact.")
        return None

    # v193: Eén blijvend willekeurig zaad, zodat een herstart niet telkens
    # dezelfde nummers eerst kiest. De volgorde wordt onafhankelijk van de
    # CSV-bestandsvolgorde bepaald (geen voordeel voor aflevering 833).
    # De cursor doorloopt vervolgens elk uniek archiefnummer maximaal eenmaal.
    raw_seed = cache.get(_SEED)
    if type(raw_seed) is not int or raw_seed < 0:
        raw_seed = secrets.randbits(64)
        cache[_SEED] = raw_seed
        # Vervang ook de oude opeenvolgende v192-cursor zonder queue-reset.
        cache[_CURSOR] = 0

    candidates.sort(key=lambda entry: entry[2])
    archive_fingerprint = hashlib.sha256(
        "\n".join(entry[2] for entry in candidates).encode("utf-8")
    ).hexdigest()
    shape = ["v193-shuffle", archive_fingerprint]
    if cache.get(_SHAPE) != shape:
        cache[_SHAPE] = shape
        cache[_CURSOR] = 0
    random.Random(raw_seed).shuffle(candidates)
    try:
        start = max(0, min(len(candidates), int(cache.get(_CURSOR, 0) or 0)))
    except (TypeError, ValueError):
        start = 0

    queued = {key_func(x.get("artist", ""), x.get("title", ""))
              for x in live_queue if isinstance(x, dict)}
    known = set(cache.get("__playlist_keys", []))
    parked = cache.get("__v50_duyster_unmatched", {})
    if not isinstance(parked, dict):
        parked = {}
    for pos in range(start, len(candidates)):
        artist, title, key = candidates[pos]
        cache[_CURSOR] = pos + 1
        if key in queued or key in seen or key in known or key in parked:
            continue
        if any(cache.get("__not_found_v" + str(version) + "__" + key) is not None
               for version in (34, 35)):
            continue
        if not allowed(artist, title):
            continue
        if in_playlist(artist, title, known):
            continue
        item = {"artist": artist, "title": title, "source": "duyster"}
        live_queue.append(item)
        cache[_NEXT] = now + DUYSTER_ENQUEUE_INTERVAL_SECONDS
        print(f"📚 Duyster 1/120s ACHTERAAN FIFO: {artist} — {title} "
              f"(Duyster-wachtend: {pending + 1}).")
        return item
    cache[_NEXT] = now + DUYSTER_ENQUEUE_INTERVAL_SECONDS
    print("ℹ️ Duyster: alle archiefkandidaten zijn verwerkt of uitgesloten.")
    return None
