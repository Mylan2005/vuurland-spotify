"""Offline regressions for recovery from ambiguous Spotify playlist POSTs."""
from v246_uncertain_spotify_append import verify_uncertain_spotify_append


def fake_playlist(size, target_at=None, changed=False, corrupt=False):
    calls = []
    def request(method, path, params=None):
        calls.append((method, path, params))
        if path.endswith("/items"):
            offset = params["offset"]
            limit = params["limit"]
            items = [
                {"item": {"uri": "spotify:track:target" if i == target_at
                           else f"spotify:track:other{i}"}}
                for i in range(offset, min(offset + limit, size))
            ]
            if corrupt and offset == 100:
                items.pop()
            return {"total": size, "items": items}
        return {"snapshot_id": "changed" if changed and len(calls) > 2 else "stable"}
    return request, calls


request, calls = fake_playlist(235, target_at=4)
assert verify_uncertain_spotify_append(request, "pl", "spotify:track:target") is True
assert len([call for call in calls if call[1].endswith("/items")]) == 3

request, _ = fake_playlist(235, target_at=234)
assert verify_uncertain_spotify_append(request, "pl", "spotify:track:target") is True
request, _ = fake_playlist(235)
assert verify_uncertain_spotify_append(request, "pl", "spotify:track:target") is False
request, _ = fake_playlist(0)
assert verify_uncertain_spotify_append(request, "pl", "spotify:track:target") is False

for request in (
    fake_playlist(235, changed=True)[0],
    fake_playlist(235, corrupt=True)[0],
):
    try:
        verify_uncertain_spotify_append(request, "pl", "spotify:track:target")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Uncertain/partial scan must fail closed")

print("✅ v246: volledige playlistcheck, snapshotveiligheid en 502-herstel.")
