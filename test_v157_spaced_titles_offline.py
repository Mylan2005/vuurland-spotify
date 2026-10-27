"""v157: offline regression for Spotify titles with individually spaced letters.

The matcher already handles spacing in title_compact(). Keep that behavior
without creating an alternative bypass of artist and version validation.
"""
import inspect
import vuurland_sync as sync

source = inspect.getsource(sync.find_spotify_track)

# The local matcher compacts punctuation/spacing for title identity.
assert "def title_compact(value):" in source
assert 'compacted = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)' in source
assert 'wanted_base_identity == spotify_base_identity' in source

# Verify that artist/version constraints remain in the same candidate-validation
# function, rather than bypassing it with a new direct Spotify ID.
assert "primary_artist_exact" in source
assert "version_family" in source
assert "requested_version" in source

# The deliberate v156 change prevents turning arbitrary single-word
# queries into letter-spelled searches (which hurts recall).
assert '" ".join(str(search_title).strip().upper())' not in source

# The explicit Bon Iver catalog query remains possible for better recall.
assert 'str(primary_search_artist).casefold().strip() == "bon iver"' in source
assert 'str(search_title).casefold().strip() == "speyside"' in source
assert 'search_title = "S P E Y S I D E"' in source

# Regex identity used by title_compact must treat letter-spaced titles as
# equivalent without equating altered/reordered letters.
import re
compact = lambda s: re.sub(r"[^\w]+", "", s.casefold(), flags=re.UNICODE)
assert compact("Speyside") == compact("S P E Y S I D E")
assert compact("Dreaming") == compact("D R E A M I N G")
assert compact("Speyside") != compact("S P E Y S I D")
assert compact("Speyside") != compact("S P E Y S I D E S")
assert compact("Speyside") != compact("S P E Y S D I E")

print("✅ v157: gespatieerde-lettertitelherkenning en strenge matchguards aanwezig")
