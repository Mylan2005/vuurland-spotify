"""Offline tests for the read-only Spotify historical catalog audit."""
import importlib.util
import json
import tempfile
from pathlib import Path

path = Path(__file__).parent / "scripts" / "vuurland_catalog_audit.py"
spec = importlib.util.spec_from_file_location("vuurland_catalog_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

yellow = {"id": "3UAok9T3sRuD3KwEA3E3fA", "name": "flowin",
          "artists": [{"name": "YellowStraps"}, {"name": "Sam Wise"}],
          "album": {"name": "Album"}}
status, candidates = audit.classify("YellowStraps", "flowin (feat. Sam Wise)", [yellow])
assert status == "same_metadata_candidate_needs_version_review"
assert candidates[0]["metadata_matches"]
status, candidates = audit.classify("YellowStraps", "flowin (feat. Another Artist)", [yellow])
assert status == "candidate_requires_manual_review"
assert not candidates[0]["metadata_matches"]
status, _ = audit.classify("YellowStraps", "flowin (feat. Sam Wise)",
                           [{**yellow, "name": "flowin - Live"}])
assert status == "candidate_requires_manual_review"
assert audit.strip_explicit_feature("flowin (f Sam Wise)") == ("flowin", "Sam Wise")
assert audit.strip_explicit_feature("Folding Stars (MTV Unplugged Live)") == (
    "Folding Stars (MTV Unplugged Live)", None)

class Response:
    status_code = 200
    def json(self):
        return {"tracks": {"items": [yellow]}}
    def raise_for_status(self):
        pass

class Session:
    calls = 0
    def get(self, *args, **kwargs):
        assert args[0].endswith("/search")
        assert kwargs["params"]["market"] == "BE"
        self.calls += 1
        return Response()

with tempfile.TemporaryDirectory() as d:
    source = Path(d) / "input.json"
    target = Path(d) / "result.jsonl"
    source.write_text(json.dumps({"tracks": [
        {"artist": "YellowStraps", "title": "flowin (feat. Sam Wise)"},
        {"artist": "Another", "title": "Other"},
    ]}))
    fake = Session()
    x = audit.audit(source, target, session=fake, token="test",
                    max_queries=2, delay=0)
    assert x["searched_now"] == 2
    assert fake.calls == 2
    x = audit.audit(source, target, session=fake, token="test",
                    max_queries=2, delay=0)
    assert x["searched_now"] == 0
    assert fake.calls == 2
    assert len(target.read_text().splitlines()) == 2

print("Read-only catalog audit offline tests passed.")
