"""v71 matcher-regressietest. Gebruikt uitsluitend nagebootste Spotify Search-data."""
import os
os.environ.setdefault('SPOTIFY_CLIENT_ID', 'offline_test')
os.environ.setdefault('SPOTIFY_CLIENT_SECRET', 'offline_test')
os.environ.setdefault('SPOTIFY_REFRESH_TOKEN', 'offline_test')
import vuurland_sync as m

def track(title, artists, tag='a'):
    return {'name': title, 'artists': [{'name': a} for a in artists],
            'external_ids': {'isrc': 'BEAAA260000'+tag},
            'uri': 'spotify:track:TEST'+tag,
            'album': {'name': 'Test Album'}}

cases = [
 ('THE ANXIETY (WILLOW & TYLER COLE)', 'Meet me at our spot',
  [track('Meet Me At Our Spot', ['THE ANXIETY','WILLOW','Tyler Cole'],'1')]),
 ('Meshell Ndegeocello', 'Don’t You Want Me (with Cat Power)',
  [track('Don’t You Want Me (with Cat Power)', ['Meshell Ndegeocello','Cat Power'],'2')]),
 ('ESKOBAR & HEATHER NOVA', 'Someone',
  [track('Someone New', ['Eskobar','Heather Nova'],'3')]),
 ('Mark Knopfler and Emmylou Harris', 'Beachcombing',
  [track('Beachcombing', ['Mark Knopfler','Emmylou Harris'],'4')]),
 ('Vince Guaraldi', 'Charlie Brown Theme',
  [track('Charlie Brown Theme', ['Vince Guaraldi Trio'],'5')]),
 ('Eurythmics', 'Here Comes the Rain Again (acoustic)',
  [track('Here Comes the Rain Again - Remastered Version', ['Eurythmics','Annie Lennox','Dave Stewart'],'6')]),
]
for artist, title, results in cases:
    m.spotify_request = lambda *args, **kwargs: {'tracks': {'items': results}}
    assert m.find_spotify_track(artist, title) == results[0]['uri'], (artist,title)

# Vier soorten uitvoeringen krijgen maximaal één opname in de playlist.
for recorded in ('The Scientist', 'The Scientist (Live)', 'The Scientist - 2019 Remaster', 'The Scientist - Radio Mix'):
    keys = m.make_playlist_keys(track(recorded, ['Coldplay']))
    for requested in ('The Scientist', 'The Scientist - Live', 'The Scientist (Remastered)', 'The Scientist - Radio Mix'):
        assert m.radio_matches_playlist('Coldplay', requested, keys), (recorded,requested)

# Soortgelijke titels mogen niet per ongeluk hetzelfde lied worden.
keys = m.make_playlist_keys(track('The Scientist Is Dead', ['Coldplay']))
assert not m.radio_matches_playlist('Coldplay','The Scientist', keys)
assert not m.v71_same_song_title('Someone', 'Someone Else', 'Eskobar & Heather Nova')
assert not m.v71_same_artist_credit('Eskobar & Heather Nova', 'Eskobar & Another Singer')

# Versieprioriteit: een live-vraag kiest live vóór gewone versie.
regular=track('The Scientist', ['Coldplay'],'7')
live=track('The Scientist - Live', ['Coldplay'],'8')
m.spotify_request = lambda *a, **kw: {'tracks': {'items': [regular, live]}}
assert m.find_spotify_track('Coldplay','The Scientist (live)') == live['uri']
# Ontbreekt de gevraagde versie, dan wordt een gewone officiële opname gekozen.
m.spotify_request = lambda *a, **kw: {'tracks': {'items': [regular]}}
assert m.find_spotify_track('Coldplay','The Scientist (live)') == regular['uri']

print('✅ v71: zes radio-cases, versiededuplicatie, negatieve cases en fallback geslaagd (offline).')
