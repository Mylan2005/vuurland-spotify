"""v101 structure and user-confirmed correction regressions (no Spotify network)."""
import re
import vuurland_sync as sync

expected = {
    ('hybris','how can our love be blind'): '0tAO41U8SChmfAZaehIhuy',
    ('noah & the whale','five years time'): '12je8giC2S9smUHJ81tpiL',
    ('the kooks','naive (live for radio x)'): '7BHPGtpuuWWsvE7cCaMuEU',
    ('zbigniew preisner & lisa gerrard','believe in yourself'): '13w23mzuktOwHzdKqtOYYV',
    ('hybris','blood flow'): '31Rl9OwQxiRk2T66rqfJfJ',
    ('josefin öhrn & the liberation','rushing through my mind (mang dynasty extended version)'): '2O5iXIhZbnusoU8au9gast',
    ('the flaming lips','do you realise?'): '1GjpSlPPKzrCFD0n8Zjhp3',
    ('xymox','imagination'): '6YVKkyrX3PkBcr5AaxrCWw',
    ('anna domino','rhythm'): '3599axkmRnbvIAGOzV0uch',
    ('giovanni battista pergolesi','stabat mater dolorosa'): '7LcypCVM2DeybABIv1Ydaa',
}
for key, value in expected.items():
    assert sync.v81_catalog_locator(*key) == value
    assert re.fullmatch(r'[A-Za-z0-9]{22}', value)
assert sync.ARTIST_ALIASES['hybris'] == ['Postiljonen']
assert sync.ARTIST_ALIASES['xymox'] == ['Clan of Xymox']
assert sync.v101_radio_x_studio_title('Naive (Live For Radio X)') == 'Naive'
assert sync.v101_radio_x_studio_title('Naive (Live at Glastonbury)') == 'Naive (Live at Glastonbury)'
assert sync.v101_safe_title_spelling('Do You Realise?') == sync.v101_safe_title_spelling('Do You Realize??')
assert sync.v101_safe_title_spelling('Do You Realise?') != sync.v101_safe_title_spelling('Do You Remember?')
assert ('nick cave', "evil ('silver alert' remix feat. matt berninger)") in sync.V101_EXCLUDED_RADIO_TRACKS
assert ('kelley polar', "entropy reigns (pearson and usher's second law dynamix)") in sync.V101_EXCLUDED_RADIO_TRACKS
for artist, title in sync.V101_EXCLUDED_RADIO_TRACKS:
    assert sync.find_spotify_track(artist, title) is None
assert sync.CHECK_EVERY_SECONDS == 60
assert sync.SPOTIFY_SEARCH_HTTP_LIMIT == 1
print('✅ v101: 10 gecontroleerde cataloguslocators, 2 uitsluitingen, alias- en titelregels, limieten.')
