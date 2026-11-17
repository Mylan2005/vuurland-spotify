"""v258: weak searches park early; promising rejections never auto-approve."""
from pathlib import Path
from v258_matcher_triage import classify_candidates, early_park_after_weak_results, record_miss

strong = [{"name":"Starts With One", "id":"abc", "artists":[{"name":"Shiny Toy Guns"}]}]
kind, preview = classify_candidates("Shiny Toy Guns", "Starts With One (Young Americans Remix)", strong)
assert kind == "promising", (kind, preview)
assert not early_park_after_weak_results(True, kind, 1)
assert classify_candidates("Sunday Girl", "Love U More (RAC Mix)", [
    {"name":"Unrelated Tune", "artists":[{"name":"Other Band"}]}
])[0] == "weak"
assert early_park_after_weak_results(True, "weak", 1)
assert not early_park_after_weak_results(False, "weak", 0)
assert not early_park_after_weak_results(True, "uncertain", 2)
assert classify_candidates("Example", "Song", [{"name":"Different", "artists":[{"name":"Example"}]}])[0] == "uncertain"
assert classify_candidates("Example", "Song", None)[0] == "uncertain"
cache = {}
for i in range(310):
    record_miss(cache, str(i), "wbru", "Artist", "Title", kind, preview, 1)
assert len(cache["__v258_matcher_triage"]) == 300
assert cache["__v258_matcher_triage"]["309"]["status"] == "review_guard"
src = Path("vuurland_sync.py").read_text(encoding="utf-8")
assert "from v258_matcher_triage import" in src
assert "LAST_SPOTIFY_TRIAGE" in src
assert "v258_early_park(" in src
assert "v51_radio_park(cache, artist, title, failed_source, count)" in src
assert "max_additions_per_round = 1" in src
assert "cache['__v150_next_spotify_round_at'] = time.time() + 120" in src
assert "safe_remix_original_fallback(" in src
print("✅ v258: low-relevance parking, promising candidate review, existing guards.")
