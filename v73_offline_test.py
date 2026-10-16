"""No Spotify calls. Tests the v73 403 response and persisted cooldown."""
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault('SPOTIFY_CLIENT_ID', 'offline-test')
with tempfile.TemporaryDirectory() as temp:
    os.environ['VUURLAND_DATA_DIR'] = temp
    spec = importlib.util.spec_from_file_location('vuurland_v73', Path(__file__).with_name('vuurland_sync.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    class Resp:
        status_code = 403
        content = b'{"error":{"message":"Forbidden"}}'
        headers = {}
        def json(self): return {'error': {'message':'Forbidden'}}
        def raise_for_status(self): raise AssertionError('403 must be handled before raise_for_status')
    with patch.object(mod, 'get_token', return_value={'access_token':'fake'}), patch.object(mod.requests, 'request', return_value=Resp()):
        try:
            mod.spotify_request('GET','/search',params={'q':'Jack Johnson Inaudible Melodies','type':'track','limit':10,'market':'from_token'})
            raise AssertionError('Should fail safely')
        except RuntimeError as err:
            assert 'Spotify HTTP 403:' in str(err), err
    stored=json.load(open(Path(temp)/'.vuurland_spotify_cache.json'))
    assert stored['__spotify_server_error_until'] > __import__('time').time()+3500
    assert mod.SPOTIFY_SEARCH_HTTP_USED == 1
print('✅ v73: 403 bewaart cooldown, verhoogt Search-teller maximaal eenmaal en verliest geen state (offline).')
