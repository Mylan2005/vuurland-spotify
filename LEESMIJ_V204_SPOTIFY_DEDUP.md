# Vuurland v204 — veilige duplicatencontrole

Gebaseerd op het **idee** van [JMPerez/spotify-dedup](https://github.com/JMPerez/spotify-dedup) (MIT; José M. Pérez, 2018). Er is geen code uit dat project gekopieerd.

Het oorspronkelijke project kan playlists en opgeslagen nummers scannen en dubbele items verwijderen. **Vuurland v204 doet dat uitdrukkelijk niet.** De gebruiker beheert deze playlist en dubbels handmatig; v185 heeft automatische volledige inventories uitgeschakeld om honderden Spotify API-requests en conflicten met de historische cache te vermijden.

## Wat werkt?

Met een expliciete, actuele JSON-export van één playlist:

```sh
python v204_spotify_dedup_review.py --input playlist-export.json --out-dir duplicaten_rapport
```

De invoer is een JSON-lijst van Spotify-trackobjecten, of items met een `track` of `item` veld, of een JSON-object met een `items`-lijst (één volledige snapshotsamenstelling). De uitvoer bevat:

- `vuurland_v204_duplicaten.json`: exacte dubbele URI's, gelijke ISRC bij verschillende URI's, en losse reviews.
- `vuurland_v204_duplicaten.md`: leesbaar overzicht met playlistposities.

De derde categorie komt van spotify-dedup: gelijke volledige artiest- en titelnaam bij een speelduurverschil **kleiner dan 2 seconden**. Deze is **alleen voor handmatige beoordeling**. Verschillende masters, liveversies, edits, covers en remixes mogen nooit automatisch samengevoegd worden op basis van duur of naam. Een ISRC-signaal is sterker maar vereist eveneens playlistcontext voordat je iets verwijdert.

## Veiligheidsgrenzen

- **Geen Spotify API-calls, geen playlistscan, geen authenticatie, geen playlistwijzigingen, geen verwijderingen.**
- Geen wijziging van de bestaande matcher, de FIFO, likes, exclusions of de historisch beschermde dedupe-cache.
- Een historische cache met verzamelde URI's en ISRC's is **geen** actuele playlist-snapshot; gebruik hem niet als invoer of bewijs van huidige dubbele tracks.
- Het script leest uitsluitend de JSON-export die je expliciet meegeeft. Er wordt niets automatisch uit GitHub Actions-artifacts gegist.
- Zonder actuele export is er nog **geen rapport van je huidige playlist**. Voor live handmatig verwijderen kan de oorspronkelijke tool worden gebruikt na controle.

Tests: `python test_v204_spotify_dedup_offline.py`.
