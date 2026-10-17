"""v78 recovery and priority tests, no Spotify calls."""
import os, tempfile, importlib.util
from pathlib import Path
with tempfile.TemporaryDirectory() as directory:
    os.environ['SPOTIFY_CLIENT_ID'] = 'offline-test'
    os.environ['VUURLAND_DATA_DIR'] = directory
    spec = importlib.util.spec_from_file_location('v78', Path(__file__).with_name('vuurland_sync.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    pairs = list(m.V78_RECOVERY_TRACKS)
    radio = [{'id':'vuurland','tracks':[pairs[4], pairs[0]]},
             {'id':'mellow_mix','tracks':[pairs[1]]}]
    parked = {m._v47_key(*pairs[i]): {'artist':pairs[i][0], 'title':pairs[i][1], 'source':'mellow_mix'} for i in (2,3)}
    cache = {'__v51_radio_unmatched':parked.copy(),
             '__v51_radio_failed_searches':{k:5 for k in parked}}
    queue = [{'artist':pairs[4][0], 'title':pairs[4][1], 'source':'vuurland', '_v34_retry_at':9999999999,
              '_v34_search_variant':2}, {'artist':'Other','title':'Song','source':'vuurland'}]
    ranks = m.v78_recover_and_prioritize(cache, queue, radio)
    assert len(queue)==6,queue
    assert len(ranks)==5
    assert queue[0]['_v34_search_variant']==0 and '_v34_retry_at' not in queue[0]
    assert not cache['__v51_radio_unmatched']
    assert not cache['__v51_radio_failed_searches']
    assert cache['__v78_recovery_initialized']
    before=list(queue)
    m.v78_recover_and_prioritize(cache, queue, radio)
    assert queue==before, 'A restart must not duplicate entries'
    # Unknown original source never fabricated.
    isolated = []
    another_cache = {}
    m.v78_recover_and_prioritize(another_cache, isolated, [])
    assert not isolated
    # After queue removal the priority naturally ends.
    queue[:] = [item for item in queue if m._v47_key(item['artist'],item['title']) != m._v47_key(*pairs[0])]
    ranks = m.v78_recover_and_prioritize(cache, queue, radio)
    assert m._v47_key(*pairs[0]) not in ranks
    print('✅ v78: herstel, broncontrole, geen dubbele queue-items, eenmalige prioriteit')
