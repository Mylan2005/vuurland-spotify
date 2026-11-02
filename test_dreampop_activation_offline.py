"""Offline regression checks for Dreampop live-source activation.

Read-only: no Spotify calls, radio requests or state modifications.
"""
import ast
from pathlib import Path

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
order = next(
    ast.literal_eval(node.value)
    for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "RADIO_SOURCE_ORDER"
            for target in node.targets)
)
assert order == (
    "vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled",
    "dreampop_radio",
), order

sync = next(node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "sync")
catalog = next(
    node.value
    for node in ast.walk(sync)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "source_catalog"
            for target in node.targets)
)
values = {
    k.value: v for k, v in zip(catalog.keys, catalog.values)
    if isinstance(k, ast.Constant)
}
assert "dreampop_radio" in values
entry = values["dreampop_radio"]
assert isinstance(entry, ast.Tuple) and len(entry.elts) == 3
assert isinstance(entry.elts[1], ast.Name)
assert entry.elts[1].id == "get_dreampop_radio_tracks"
assert isinstance(entry.elts[2], ast.Constant)
assert entry.elts[2].value == "__last_radio_key_dreampop_radio"

collector = next(node for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == "v96_collect_live_plays")
collector_source = ast.get_source_segment(source, collector)
assert 'old = snapshots.get(sid)' in collector_source
assert 'if sid in RADIO_SOURCE_ORDER:' in collector_source
assert 'arrivals = []' in collector_source
assert 'snapshots[sid] =' in collector_source

print("OK: Dreampop is fifth source, parser wired, first snapshot is baseline")
