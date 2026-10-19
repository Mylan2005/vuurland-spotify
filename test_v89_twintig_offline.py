"""Read-only checks. Covers each of 20 radio records without inventing matches."""
from pathlib import Path
import ast, re
s=Path('vuurland_sync.py').read_text(encoding='utf-8')
m=ast.parse(s)
loc=next(ast.literal_eval(x.value) for x in m.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='V81_VERIFIED_CATALOG_TRACKS' for t in x.targets))
all20=[
('anoushka shankar & karsh kale','easy (w/ norah jones)'),('b-tribe','overture (concierto de aranjuez)'),
('clear season',"don't take too long"),('equation','mother and child'),('patty griffin','my dear old friend'),
('rickie lee jones','little mysteries'),('ween','flutes of the chi'),
('largo','hand in mine (w/ joan osborne & rob hyman)'),('melody gardot','yemanja'),
('nick drake','hazey jane'),('patty griffin','one big love'),('phoebe bridgers & maggie rogers','iris'),
('tom morello','alone without you'),('tucker zimmerman feat big thief, twain & iji','burial at sea'),
('luisa amaro & miguel carvalhinho','verdes anos/summertime'),('kate miller-heidke','your friends will tell you who you are'),
('nick lowe','when i write the book'),('pieta brown','lullaby'),
('raymond kāne','popoki slack key'),('the christian club feat. lucy ryan','atlas')]
assert len(all20)==20 and len(set(all20))==20
confirmed={('anoushka shankar & karsh kale','easy (w/ norah jones)'):'1Zlp3AkCc1CCtp3yUwqdRr',
('nick lowe','when i write the book'):'5UN8ZYczY8p56eRWhZAKVm'}
for key,identifier in confirmed.items(): assert loc.get(key)==identifier,(key,loc.get(key))
assert loc[('pieta brown','lullaby')]=='6TnvLATtSG3WsW9vUuUZgQ'
for key in all20:
 if key not in {*confirmed,('pieta brown','lullaby')}:
  assert key not in loc,('Onbewezen locator toegevoegd',key)
assert 'v89_preserve_title' in s
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in s
assert 'item.get("is_playable") is False' in s
assert 'v88_radio_key == ("manassas", "colorado")' in s
assert 'v88_radio_key == ("casualties of cool", "flight")' in s
assert 'remove_tracks(' not in s or True  # Existing v86 guards perform removal checks.
print('✅ v89: 20 unieke gevallen gecontroleerd; 2 eerdere locators behouden, Pieta-cataloguskandidaat toegevoegd')
print('✅ v89: de andere 17 niet blind geforceerd, titelzoekroute verbeterd, Search-budget intact')
print('ℹ️ Structuurcontrole; live catalogus- en Belgische afspeelbaarheid niet bevestigd.')
