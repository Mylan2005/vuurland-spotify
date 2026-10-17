"""v75 offline regressietest, geen internet of Spotify-mutaties."""
import os
os.environ['SPOTIFY_CLIENT_ID']='offline'
import vuurland_sync as m

def track(title, artist='Sons of the East', tag='X', playable=True):
    return {'name':title,'artists':[{'name':artist}], 'uri':'spotify:track:OFFLINE'+tag,
            'is_playable':playable,'album':{'name':'Test album'},'external_ids':{'isrc':'TEST'+tag}}

def check(wanted, results, expected, artist='Sons of the East'):
    m.spotify_request=lambda *a,**k:{'tracks':{'items':results}}
    found=m.find_spotify_track(artist,wanted)
    assert found==expected,(wanted,found,expected)

original=track('Into The Sun',tag='ordinary')
ep=track('Into The Sun - EP Version',tag='ep')
edit=track('Into The Sun - Radio Edit',tag='edit')
live=track('Into The Sun - Live',tag='live')
remaster=track('Into The Sun - 2020 Remastered',tag='remaster')
single=track('Into The Sun - Spotify Singles',tag='single')
check('Into The Sun',[edit,ep,original,remaster],original['uri'])
check('Into The Sun - Live',[live,ep,original],original['uri'])
check('Into The Sun',[edit,ep],ep['uri'])
check('Into The Sun',[single],single['uri'])
check('Into The Sun',[ep,original],original['uri'])
check('Into The Sun',[track('Into The Sun - EP Version',tag='blocked',playable=False),edit],edit['uri'])
check('Into The Sun',[track('Into The Sun is Gone',tag='wrong')],None)
check('Into The Sun',[track('Into The Sun',artist='Another Band',tag='wrong')],None)
check('King of Everything',[track('King of Everything',artist='Dominic Fike',tag='dom')],'spotify:track:OFFLINEdom',artist='Dominic Fike')
print('✅ v75: gewone versie voorrang, EP, edit, Spotify Singles, live, regio en foute titels/artiesten offline getest')
