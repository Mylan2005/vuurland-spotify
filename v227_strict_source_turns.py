"""v227: één eerlijke Spotify-beurt per bron, onafhankelijk van queuegrootte.

Kies uitsluitend bronnen met minstens één zoekklaar FIFO-item. Verander geen
wachtrij of andere status. Een leeg/volledig gecooldownd station verbruikt
geen Spotify Search. De volgende verse beurt begint na de vorige bron.
"""


def next_source_turn(queue, source_order, last_source, ready):
    """Return (source, number of eligible items), or (None, 0)."""
    sources = tuple(source_order)
    if not sources:
        return None, 0
    counts = {source: 0 for source in sources}
    for item in queue:
        if not isinstance(item, dict) or not item:
            continue
        source = str(item.get("source") or "vuurland").strip()
        if source not in counts:
            continue
        if ready(item):
            counts[source] += 1
    start = ((sources.index(last_source) + 1) % len(sources)
             if last_source in sources else 0)
    for offset in range(len(sources)):
        source = sources[(start + offset) % len(sources)]
        if counts[source]:
            return source, counts[source]
    return None, 0
