# v197 — Oude matcher-rapporten samen analyseren

Met deze **offline** tool kun je tientallen gedownloade GitHub Actions
matcher-rapporten samenvoegen zonder Spotify API, playlist- of FIFO-wijzigingen.

1. Download oudere `vuurland_matcher_rapport`-artifacts van GitHub Actions.
2. Pak de ZIP-bestanden uit in een lokale map, bijvoorbeeld `oude_rapporten/`.
3. Voer uit vanuit de repository:

   ```bash
   python v197_combine_matcher_reports.py --input-dir oude_rapporten --out-dir overzicht_v197
   ```

De tool zoekt recursief naar CSV- en JSON-bestanden met `matcher` en
`rapport` of `report` in de bestandsnaam.

Resultaat:
- `v197_gecombineerd.csv`: sorteerbaar lijstje;
- `v197_gecombineerd.json`: machineleesbaar;
- `v197_gecombineerd.md`: overzicht met aantallen en fouten.

**Belangrijk:** het aantal rapporten is niet noodzakelijk het aantal unieke
GitHub-runs: een JSON en een CSV uit dezelfde run kunnen dubbel tellen.
Gebruik daarom bij voorkeur één bestandsformaat per run. De tool groepeert
alleen op exact overeenkomende artiest/titel na Unicode-, hoofdletter- en
spatiecorrectie. Live, remix en andere uitvoeringsversies worden niet
samengevoegd. Een afgewezen Spotify-kandidaat is geen goedgekeurde match.

De tool haalt oude GitHub-artifacts niet automatisch op. Je moet ze eerst
zelf downloaden of aanleveren. Geen verzamelde rapporten? Dan wordt een
leeg rapport gemaakt zonder nummers te verzinnen.
