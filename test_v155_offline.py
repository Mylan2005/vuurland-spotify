"""Offline regressietest voor mobiele Spotify-uitsluitingen. Geen netwerk of Spotify."""
import json
import re
from pathlib import Path

import vuurland_sync as sync

data = json.loads(Path("vuurland_user_exclusions.json").read_text(encoding="utf-8"))
assert isinstance(data, dict)
assert isinstance(data.get("ids"), list)
assert isinstance(data.get("pairs"), list)
assert all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9]{22}", x) for x in data["ids"])
assert len(data["ids"]) == len(set(data["ids"]))
assert all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, str) and v.strip() for v in p)
           for p in data["pairs"])
assert all(tuple(p) in sync.V101_EXCLUDED_RADIO_TRACKS for p in data["pairs"])
assert set(data["ids"]) == sync.V155_EXCLUDED_SPOTIFY_IDS

# Historische handmatige blokkering en de eerste mobiele uitsluiting blijven actief.
assert ("tones and i", "dance monkey") in sync.V101_EXCLUDED_RADIO_TRACKS
assert "2XU0oxnq2qxCpomAAuJY8K" in sync.V155_EXCLUDED_SPOTIFY_IDS
print("✅ Mobiele Spotify-uitsluitingen: JSON, ID-guard en oude blokkeringen OK")
