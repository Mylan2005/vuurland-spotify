"""Offline checks for weekly Duyster import and interview/session exclusions."""
import csv
import io
import json
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import requests

from duyster_archive_fifo import is_non_music_title
from duyster_weekly_update import get_episode, update_archive, read_archive


def page(pid, songs, date="02-11-2026"):
    links = []
    for artist, title in songs:
        uri = "/library/songs.php?" + urlencode({"Artiest": artist, "Titel": title})
        links.append(f'<a href="{uri.replace("&", "&amp;")}">{artist} {title}</a>')
    return (f"<html><h2>{date}</h2><p>playlist nr. {pid}</p>"
            + "<h5>22u00-23u00</h5>"
            + "\n".join(links) + "</html>")


class Response:
    def __init__(self, status_code, html=""):
        self.status_code = status_code
        self.text = html

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


playlist_834 = [
    ("Mogwai", "Remurdered"),
    ("Shearwater", "Rooks"),
    ("Some Guest", "Interview"),
    ("Other Guest", "Sessie"),
    ("Yet Another Guest", "Interview + Sessie"),
    ("New Artist", "Night and Morning"),
    ("Blanco White", "Mano a Mano"),
    ("Recording Artist", "Radio 1 Sessie"),  # echte opname mag blijven
]

def mock_get(url, **kwargs):
    assert kwargs["timeout"] == 15
    if url.endswith("pid=834"):
        return Response(200, page(834, playlist_834))
    if url.endswith("pid=835"):
        return Response(404)
    raise AssertionError(url)


episode = get_episode(834, request_get=mock_get)
assert episode and episode["pid"] == 834
assert len(episode["songs"]) == 5
assert episode["skipped_non_music"] == 3
assert ("Recording Artist", "Radio 1 Sessie") in episode["songs"]
assert get_episode(835, request_get=mock_get) is None
assert get_episode(834, request_get=lambda *_args, **_kwargs:
                   Response(200, page(833, playlist_834))) is None
for entry in ("Interview", "Sessie", "Interview + Sessie", "interview & sessie"):
    assert is_non_music_title(entry)
assert not is_non_music_title("Radio 1 Sessie")

with tempfile.TemporaryDirectory() as tmp:
    archive = Path(tmp) / "duyster_archief_uniek.csv"
    state_file = Path(tmp) / "duyster_archief_import_state.json"
    with archive.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(("artist", "title", "first_seen_pid", "seen_in"))
        writer.writerow(("Mogwai", "Remurdered", 553, 10))
        writer.writerow(("Shearwater", "Rooks", 344, 13))
    state_file.write_text(json.dumps({"next_pid": 834, "last_imported_pid": 833}) + "\n",
                          encoding="utf-8")
    def website(pid):
        return get_episode(pid, request_get=mock_get)

    assert update_archive(archive=archive, state_file=state_file, get_page=website) == 1
    rows, keys = read_archive(archive)
    assert len(rows) == 5, rows
    assert rows[0]["seen_in"] == "11"
    assert rows[1]["seen_in"] == "14"
    assert rows[2]["title"] == "Night and Morning"
    assert all(not is_non_music_title(row["title"]) for row in rows)
    assert rows[2]["first_seen_pid"] == "834"
    assert rows[4]["title"] == "Radio 1 Sessie"
    assert state_file.read_text(encoding="utf-8").find('"next_pid": 835') >= 0
    before = archive.read_bytes()
    before_state = state_file.read_bytes()
    assert update_archive(archive=archive, state_file=state_file, get_page=website) == 0
    assert archive.read_bytes() == before
    assert state_file.read_bytes() == before_state

    # Een niet-gepubliceerde pagina/redirect is geen bevestigde nieuwe aflevering.
    def wrong_episode(pid):
        return get_episode(pid, request_get=lambda *_args, **_kwargs:
                           Response(200, page(834, playlist_834)))
    assert update_archive(archive=archive, state_file=state_file, get_page=wrong_episode) == 0
    assert state_file.read_bytes() == before_state

    # Nog een echte aflevering komt volgende woensdag binnen, achter 834.
    playlist_835 = [
        ("Grouper", "Heavy Water/I'd Rather Be Sleeping"),
        ("New Artist", "Night and Morning"),  # reeds in 834, verhoog teller
        ("One More", "Haunting New Track"),
        ("Two More", "Dreams"), ("Three", "Falling"),
        ("Interviewer", "Interview"),
    ]
    def next_week(pid):
        return {"pid": 835, "songs": playlist_835[:5],
                "skipped_non_music": 1, "date": "09-11-2026"} if pid == 835 else None
    assert update_archive(archive=archive, state_file=state_file, get_page=next_week) == 1
    newrows, _ = read_archive(archive)
    assert len(newrows) == 9
    assert next(x for x in newrows if x["title"] == "Night and Morning")["seen_in"] == "2"
    assert json.loads(state_file.read_text(encoding="utf-8"))["next_pid"] == 836

print("✅ Duyster woensdag: episode 834/835 herkend, unieke tracks en seen_in bijgewerkt.")
print("✅ Interview, Sessie, Interview + Sessie nooit in het archief; echte livesongs blijven.")
print("✅ Ongepubliceerde aflevering wijzigt geen CSV of cursor; geen Spotify API gebruikt.")
