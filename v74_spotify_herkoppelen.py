#!/usr/bin/env python3
"""Eenmalige Spotify-toestemming voor Search; wijzigt GEEN playlist of sync-state."""
import getpass
import os
import subprocess
import tempfile


def main():
    print("🔥 Vuurland v74 — Spotify Search opnieuw toestemming geven")
    print("Deze hulp voegt geen nummers toe en past je bestaande queue niet aan.")
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not client_id:
        client_id = input("Spotify Client ID (GEEN client secret): ").strip()
    if not client_id:
        raise SystemExit("Client ID ontbreekt.")
    os.environ["SPOTIFY_CLIENT_ID"] = client_id
    # Werk in een tijdelijk mapje; niet de bestaande cache/token/queue aanpassen.
    with tempfile.TemporaryDirectory(prefix="vuurland-v74-auth-") as directory:
        os.environ["VUURLAND_DATA_DIR"] = directory
        import vuurland_sync as app
        print("\nOpen de Spotify-toestemmingspagina in je browser en keur goed.")
        print("Je Spotify Developer Dashboard moet redirect URI http://127.0.0.1:8888/callback toestaan.")
        token = app.spotify_login()
        granted = set((token.get("scope") or "").split())
        if "user-read-private" not in granted:
            raise SystemExit("Spotify gaf user-read-private niet terug. Geen token kopiëren.")
        refresh = token.get("refresh_token")
        if not refresh:
            raise SystemExit("Spotify gaf geen nieuwe refresh-token terug.")
        try:
            subprocess.run(["pbcopy"], input=refresh, text=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise SystemExit("Kon token niet naar klembord kopiëren. Geef de fout door, geen token delen.")
        print("\n✅ user-read-private is toegekend en nieuwe refresh-token staat op je Mac-klembord.")
        print("Ga naar GitHub → Settings → Secrets and variables → Actions")
        print("Werk SPOTIFY_REFRESH_TOKEN bij: plak met Cmd+V, klik Update secret.")
        print("De token wordt bewust niet afgedrukt. Deel hem nooit in de chat.")
        print("Wis na het opslaan je klembord, bijvoorbeeld met: printf '' | pbcopy")


if __name__ == "__main__":
    main()
