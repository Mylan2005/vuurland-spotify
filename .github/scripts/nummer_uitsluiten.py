"""Handle owner-authored GitHub exclusion requests without Spotify API calls."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
issue = event["issue"]
assert issue["user"]["login"].casefold() == os.environ["GITHUB_REPOSITORY_OWNER"].casefold(), "Not repository owner"
assert issue["title"].startswith("[Uitsluiten]"), "Not an exclusion request"
body = issue.get("body") or ""

def field(label):
    match = re.search(r"(?m)^### " + re.escape(label) + r"\s*\n(.*?)(?=\n### |\Z)", body, flags=re.S)
    return (match.group(1).strip() if match else "").replace("_No response_", "").strip()

url = field("Spotify-link")
parsed = urlparse(url)
if parsed.scheme != "https" or parsed.netloc.lower() != "open.spotify.com":
    raise SystemExit("Gebruik een volledige https://open.spotify.com/track/... link")
track_match = re.fullmatch(r"/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})/?", parsed.path)
if not track_match:
    raise SystemExit("Dit is geen geldige Spotify-tracklink")
track_id = track_match.group(1)
artist = field("Artiest (optioneel)")
title = field("Titel (optioneel)")
if bool(artist) != bool(title):
    raise SystemExit("Vul zowel artiest als titel in, of laat beide leeg")
if artist and (len(artist)>150 or len(title)>200):
    raise SystemExit("Artiest of titel te lang")

path = Path("vuurland_user_exclusions.json")
data = json.loads(path.read_text(encoding="utf-8"))
data.setdefault("ids", [])
data.setdefault("pairs", [])
if track_id not in data["ids"]:
    data["ids"].append(track_id)
if artist:
    pair = [" ".join(artist.casefold().split()), " ".join(title.casefold().split())]
    if pair not in data["pairs"]:
        data["pairs"].append(pair)
data["ids"].sort()
data["pairs"].sort()
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("✅ Spotify-ID toegevoegd aan uitsluitingslijst:", track_id)
