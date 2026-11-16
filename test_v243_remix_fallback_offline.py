"""Explicit remix preference and safe original-version fallback, offline."""
from pathlib import Path
from v243_remix_fallback import safe_remix_original_fallback as allowed

args = dict(requested_version="remix", candidate_version=None,
            search_variant=1, primary_artist_exact=True,
            all_credits_present=True, requested_base="Yet Again",
            candidate_base="Yet Again")
assert allowed(**args)
assert allowed(**{**args, "candidate_version": "remaster"})
assert allowed(**{**args, "requested_version": "mix"})
for change in (
    {"search_variant": 0},
    {"candidate_version": "remix"},
    {"candidate_version": "live"},
    {"candidate_version": "acoustic"},
    {"candidate_version": "karaoke"},
    {"primary_artist_exact": False},
    {"all_credits_present": False},
    {"candidate_base": "Yet Again Tomorrow"},
    {"requested_base": ""},
    {"requested_version": "live"},
):
    assert not allowed(**{**args, **change}), change
assert allowed(**{**args, "requested_base": "The World's End",
                  "candidate_base": "The Worlds End"})
source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert "v243_remix_original = safe_remix_original_fallback(" in source
assert 'elif wanted_family == "mix":' in source
assert '["ordinary", "remaster"] if v243_remix_original else []' in source
assert "if (not v243_remix_original and not v211_version_guard(" in source
assert "if wanted_family == \"mix\" and candidate_family != \"mix\" and not v243_remix_original:" in source
print("✅ v243: remix first, later exact studio fallback, no unrelated versions.")
