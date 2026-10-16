import os
import re
from pathlib import Path

code = Path("vuurland_sync.py").read_text(encoding="utf-8")
scopes = re.search(r"(?ms)^SCOPES = \(.*?^\)", code)
assert scopes, "Geen SCOPES-definitie"
assert "user-read-private" in scopes.group(0), "Spotify Search-scope ontbreekt"
assert '"market": "from_token"' in code, "Regiocontrole ontbreekt"
helper = Path("v74_spotify_herkoppelen.py").read_text(encoding="utf-8")
assert 'tempfile.TemporaryDirectory' in helper
assert 'app.spotify_login()' in helper
compile(code, "vuurland_sync.py", "exec")
compile(helper, "v74_spotify_herkoppelen.py", "exec")
print("✅ v74: scope, regiocontrole, herautorisatiehulp en syntax geslaagd (offline).")
