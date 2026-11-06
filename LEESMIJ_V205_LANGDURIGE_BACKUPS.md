# Vuurland v205 — back-up- en herstelplan voor de lange termijn

**Doel:** de muziekgeschiedenis, oorspronkelijke radioherkomst, FIFO-volgorde, matcherregistraties, uitgesloten nummers en handmatige Duyster-beslissingen behouden, ook als GitHub, de Spotify-API of de sync onderbroken wordt.

## Wat is ingesteld?

De workflow `.github/workflows/vuurland-v205-lifetime-backup.yml` kan dagelijks en handmatig worden gestart. Ze haalt een **commit-consistente** kopie van GitHub `main` op: een afzonderlijke checkout, niet de tijdelijke halfgeschreven bestanden van een draaiende runner.

1. Controleer de kritische JSON- en archiefbestanden. Ontbrekende of beschadigde kritische state = back-up mislukt.
2. Pak alleen de expliciet toegestane state-, archief- en beslissingsbestanden in. Geen Spotify-tokens, `.env` of willekeurige mappen.
3. Maak een manifest met SHA-256 per bestand, grootte, UTC-tijd en exacte Git-commit.
4. Controleer het archief opnieuw en voer een **herstelproef naar een nieuwe testmap** uit. Er is geen automatische write-back naar de actieve GitHub-state.
5. Bewaar een downloadbaar GitHub Actions-artifact (90 dagen, afhankelijk van GitHub-retentie).
6. Als een afzonderlijke AWS S3-bucket en OIDC-rol zijn ingericht, verstuur dan **dezelfde** back-up met server-side AES256-encryptie buiten GitHub.

**Belangrijk:** zolang de drie externe opslagvariabelen ontbreken, bestaat alleen de GitHub-back-up. GitHub-artifacts zijn tijdelijk en vormen **niet** het beloofde onafhankelijke archief.

## Externe opslag activeren (eenmalig door eigenaar)

Maak een **private** S3-bucket in je eigen AWS-account, buiten GitHub. Aanbevolen: S3 Versioning, Object Lock (indien gewenst), Block Public Access, bewaarbeleid, MFA op AWS-account en een aparte offsite herstelkopie. Deze instellingen zijn **nog niet automatisch uitgevoerd**.

Maak een AWS OIDC IAM-rol met vertrouwensrelatie voor GitHub Actions van repository `Mylan2005/vuurland-spotify` op branch `main`. Beperk de rol tot het schrijven van objecten onder `vuurland-lifetime/` in deze ene bucket. Geef bij voorkeur **geen** verwijder-, list- of andere brede toegangsrechten. Bewaar nooit langlevende AWS-wachtwoorden in de repo.

Stel in GitHub **Settings → Secrets and variables → Actions → Variables** in:

| Variable | Waarde |
|---|---|
| `VUURLAND_BACKUP_S3_BUCKET` | exacte private S3-bucketnaam |
| `VUURLAND_BACKUP_AWS_ROLE_ARN` | ARN van toegewezen AWS OIDC-rol |
| `VUURLAND_BACKUP_AWS_REGION` | AWS-regio van de bucket (bv. `eu-west-1`) |

Bij foutieve AWS-configuratie faalt de offsite-stap zichtbaar. Zolang de variabelen ontbreken, meldt de workflow expliciet dat offsite-back-up **niet actief** is.

## Herstellen zonder verlies van nieuwere state

Download een geverifieerde `vuurland-*.tar.gz` uit het GitHub-artifact of de S3-bucket. Controleer deze op een veilige computer:

```sh
python v205_lifetime_backup.py verify --archive vuurland-YYYYMMDDTHHMMSSZ-SHA.tar.gz
python v205_lifetime_backup.py stage-restore --archive vuurland-YYYYMMDDTHHMMSSZ-SHA.tar.gz --destination ./vuurland-herstel-inspectie
```

De herstelmap **moet nieuw zijn**. Dit script kan nooit zelf de actieve sync, de huidige repositorybestanden of Spotify overschrijven.

Wanneer de echte state hersteld moet worden:

1. Stop/pauzeer eerst de live sync en alle parallelle schrijfprocessen.
2. Vergelijk de herstelde versie en de huidige `main`-status. Leg nieuwe radioplays, wachtrijvolgnummers, Spotify-playlistgeschiedenis, uitsluitingen en handmatige beslissingen naast elkaar.
3. Zet **nooit** automatisch een oudere back-up over een nieuwere state. Laat de herstelkeuze en noodzakelijke merges expliciet nakijken.
4. Maak een nieuwe PR met de geselecteerde bestanden en draai de offline regressietests. Controleer daarna pas de live sync.

## Wat dit wel en niet garandeert

- Wel: een dagelijks back-upplan met SHA-256-verificatie, een testherstel en een downloadbare kopie, plus een **klaargezette** externe opslagroute.
- Niet: permanente garantie dat GitHub, Spotify of S3 eeuwig blijven bestaan.
- Niet: offsite-opslag vóór de eigenaar de externe opslag heeft verbonden.
- Niet: automatische automatische restoration of exacte live-Spotifyplaylist-snapshots. De back-up is een **momentopname van de gepubliceerde repository-state**.
- Niet: sleutels, Spotify-authenticatie of volledige onbeschikbare radiobronnen in het archief.

De eigenlijke Spotify-sync en het aantal API-aanvragen blijven ongewijzigd.

Offline test: `python test_v205_lifetime_backup_offline.py`.
