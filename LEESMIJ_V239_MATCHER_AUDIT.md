# Vuurland v239 — audit van 27 gemelde niet-gevonden nummers

Bron: door gebruiker aangeleverd RadioBox/Spotify-overzicht van 15 november 2026. **Dit is geen onafhankelijke Spotify-cataloguscheck.** Een gemiste match bewijst niet dat de track op Spotify staat, noch dat een Spotify-resultaat de juiste opname is.

Matcherverbeteringen gelden algemeen voor vergelijkbare titels en zijn geen hardcoded Spotify-URI-mappings. Voor de 26 bruikbare gemelde items is de bestaande v203-herkansingsroute aangevuld: die vereist nog altijd een oorspronkelijke cache-foutregistratie met echte radiobron, geldige bronkey, toelaatbaarheid, queuecapaciteit en vrije wachtrijbeurt. Bij ontbreken van die brongegevens wordt **niets gefabriceerd**. Een record wordt slechts éénmaal per nieuwe regel opnieuw ingepland, maximaal één per zes uur. Het wordt achteraan de FIFO geplaatst; dit is geen onmiddellijke zoekactie of toestemming om toe te voegen.

| Bron | Oorspronkelijk gemist nummer | Mogelijke oorzaak / bewijsstatus | Actie |
|---|---|---|---|
| Dreampop | Josh Rouse — Streetlights | Samengestelde woordspatie; bestaande v235-zoekvariant | herschrijf alleen zoekterm; controle blijft |
| DKFM Edge | Indoor Voices — Care Too Much | Geen bewezen vormfout | normale veilige herkansing |
| Dreampop | The Tallest Man On Earth — Where Do My Bluebirds Fly | Geen bewezen vormfout | normale veilige herkansing |
| Dark Edge | Étienne de Crécy with Alex Gopher — Smile | Mogelijk verschil in volledige samenwerkingscredits | alle credits verplicht; review |
| DKFM Shoegaze | Lilac — Sun | Zeer korte, ambigue artiest/titel | geen fuzzy toestemming; review |
| Indie Select | Le Boeuf Brothers — Red Velvet (Yellow Then Blue Remix) | Specifiek benoemde remix | exacte remix verplicht; review |
| IgnoreRadio | zlap. — sunlight | Mogelijk artiestpunctuatie | normale veilige herkansing |
| Dreampop | Haruko — Man In The Moon | Geen bewezen vormfout | normale veilige herkansing |
| Duyster | Maria Taylor — Two of Those Too | Mogelijk titelschrijfverschil, niet bewezen | normale veilige herkansing |
| Dreampop | On And On — Ghosts | Korte generieke titel | geen losse artiest- of titelmatch |
| Indie Select | Smashing Pumpkins — Tom Tom | Mogelijk optioneel lidwoord voor bandnaam | normale veilige herkansing |
| DKFM Edge | Hotline TNT — Spot Me 100 | Geen bewezen vormfout | normale veilige herkansing |
| Gri Balkon | Seekae — 3 (Three) | Dubbele cijferomschrijving | v239: zoeken op 3; exacte identiteit |
| egoFM Chillout | Rochus Grolle & Michael Noack feat. Alex Landon — Why | Meerdere expliciete artiestcredits | alle credits verplicht; review |
| DKFM Edge | Blush — Blush-Lover-s-Speed | Radiointerpunctie -s- mogelijk apostrof | v239: enkel veilige zoekhint |
| egoFM R&B | GoldLink x Hare Squead — Herside Story | x als duo-verbinder | v233/v238: alle credits verplicht |
| DJ Neihtul | Florence and the Machine — Flakes (Mystery Jets cover) | Expliciet coverlabel | cover niet automatisch door origineel vervangen |
| Dreampop | Ollie Brown — Midnight Call | Geen bewezen vormfout | normale veilige herkansing |
| egoFM Chillout | Kyle Dixon & Michael Stein — Stranger Things Theme (Extended) | Theme / Extended gescheiden in catalogus | v239: zoekhint en alleen dezelfde Extended-versie |
| DKFM Shoegaze | Olympic Swimmers — Apples and Pears | Geen bewezen vormfout | normale veilige herkansing |
| DJ Neihtul | Fenech-Soler — Lies (Original) | Original als radioversielabel | v239: zoekhint; versie nog verplicht |
| IgnoreRadio | Arcana Arcade — Clock Said All Aboard | Geen bewezen vormfout | normale veilige herkansing |
| Dreampop | Torpus & the Art Directors — The story's all the same | Apostrof/casing, reeds deels genormaliseerd | normale veilige herkansing |
| Duyster | Morse-achtige ongeldige artiest/titel | Beschadigde of niet-muzikale archiefregel | NIET opnieuw inplannen |
| Dreampop | Grizzly Bear — Boy From School (Hot Chip Cover) | Expliciet coverlabel | cover niet door andere versie vervangen |
| DKFM Shoegaze | Erik Blood — Share Your Love | Geen bewezen vormfout | normale veilige herkansing |
| egoFM R&B | Gallant feat. Sufjan Stevens & Rebecca Sugar — Toogoodtobetrue | Titel zonder spaties; verplichte gasten | normale veilige herkansing, alle artiestcredits |

## Beperkingen

- Geen geverifieerde Spotify-IDs, ISRC's, speelbaarheid of live API-resultaten voor deze 27 gevallen in deze wijziging.
- Remixen, covers, alternatieve uitvoeringen en expliciete gastartiesten mogen nooit door een gewoner nummer van dezelfde artiest worden vervangen zonder volledig bewijs.
- Door het zesuurslot kunnen zelfs 26 geldige, geparkeerde missers meerdere dagen nodig hebben; items zonder authentieke foutregistratie worden niet ingepland.
- De nieuwe tests controleren alleen regels en replayveiligheid. Een groene GitHub Actions-run én echte nieuwe Spotify-toevoegingen moeten apart worden bevestigd.
