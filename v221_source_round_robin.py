"""Eerlijke, herstartbestendige bronrotatie voor de gedeelde Vuurland-wachtrij.

Dit verandert geen queue-item, FIFO-volgnummer, Spotify-budget of cachebeleid.
Binnen elke bron geldt strikt de bestaande _v116_fifo_seq; tussen bronnen
krijgt de eerstvolgende bron na de laatst verwerkte bron voorrang.
"""


def fair_source_candidates(queue, source_order, last_source):
    """Geef (index, item) in bronrotatie, met FIFO binnen iedere bron.

    Onbekende bron of ongeldige queue-items blijven buiten de selectie;
    de bestaande aanvoer- en validatieregels blijven de bron van waarheid.
    """
    sources = tuple(source_order)
    if not sources:
        return []
    groups = {source: [] for source in sources}
    for index, item in enumerate(queue):
        if not isinstance(item, dict) or not item:
            continue
        source = str(item.get("source") or "vuurland").strip()
        if source in groups:
            groups[source].append((index, item))
    for group in groups.values():
        group.sort(key=lambda pair: (pair[1].get("_v116_fifo_seq", 10**30), pair[0]))

    start = ((sources.index(last_source) + 1) % len(sources)
             if last_source in sources else 0)
    rotated = sources[start:] + sources[:start]
    candidates = []
    depth = 0
    while True:
        added = False
        for source in rotated:
            if depth < len(groups[source]):
                candidates.append(groups[source][depth])
                added = True
        if not added:
            return candidates
        depth += 1
