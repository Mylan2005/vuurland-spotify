from pathlib import Path
import ast, re
src=Path('vuurland_sync.py').read_text(encoding='utf-8')
ast.parse(src)
required={
('anoushka shankar & karsh kale','easy (w/ norah jones)'):'1Zlp3AkCc1CCtp3yUwqdRr',
('casualties of cool','flight'):'73qdi1UuN5aHXwG2trXim4',
('gabriels','angels & queens'):'3C0kO7Bc51DEcJMep1deQg',
('jordan rakei & jalen ngonda','what it gave me'):'40QovgBEbr3XnqTJA55jLC',
('manassas','colorado'):'6VyuVYEJnZmlEQ5GT9LQvT',
}
module=ast.parse(src)
fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='v81_catalog_locator')
assignment=next(n for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='V81_VERIFIED_CATALOG_TRACKS' for t in n.targets))
locators=ast.literal_eval(assignment.value)
for pair,track_id in required.items():
    assert locators.get(pair)==track_id,(pair,locators.get(pair))
    assert re.fullmatch(r'[a-zA-Z0-9]{22}',track_id)
print('✅ v88: 5 exacte door gebruiker bevestigde tracks als GET-locator')
for pair in [('beth orton',"don't wanna know 'bout evil"),('bird york','haunting you'),('joan osborne','do i ever cross your mind'),('kate miller-heidke','your friends will tell you who you are'),('raymond kāne','popoki slack key')]:
    assert pair not in locators,pair
print('✅ v88: 5 onbevestigde nummers niet geforceerd')
assert 'v88_radio_key == ("casualties of cool", "flight")' in src
assert 'artist = "Devin Townsend & Ché Aimee Dorval"' in src
assert 'v88_radio_key == ("manassas", "colorado")' in src
assert 'artist = "Stephen Stills"' in src
assert 'item.get("id") != "6VyuVYEJnZmlEQ5GT9LQvT"' in src
assert '!= "manassas"' in src
assert 'item.get("is_playable") is False' in src
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in src
assert '"market": "from_token"' in src
print('✅ v88: albumcontrole, beperkte credits, regio- en Search-budget guards aanwezig')
print('ℹ️ Dit zijn offline structuurcontroles, geen Spotify-eindtest.')
